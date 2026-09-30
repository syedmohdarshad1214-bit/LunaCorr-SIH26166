"""Explicit PDS4 geom:Footprint_Vertices profile and local lunar intersections.

ISDA corner profiles follow inspected PRADAN catalogue metadata; validation against
original downloaded Chandrayaan XML labels is still pending.
Unsupported or ambiguous geometry raises GeometryUnresolved, never no-overlap.
"""

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from pyproj import CRS, Geod, Transformer
import pyproj
from shapely.geometry import Polygon, mapping
from shapely.validation import explain_validity
import shapely

from src.ingest.manifest import sha256_file


PDS = 'http://pds.nasa.gov/pds4/pds/v1'
GEOM = 'http://pds.nasa.gov/pds4/geom/v1'
ISDA = 'https://isda.issdc.gov.in/pds4/isda/v1'
PROFILES = ('geom_vertices', 'isda_system_corners', 'isda_refined_corners', 'isda_corrected_corners')


class GeometryUnresolved(ValueError):
    """Missing, unsupported, or inconsistent metadata; not proof of no overlap."""


@dataclass
class Footprint:
    product_id: str
    vertices: list
    context: dict
    label_sha256: str
    label_name: str
    profile: str = 'geom_vertices'


def validate_context(context):
    required = {
        'target', 'radius_m', 'datum', 'frame', 'longitude_direction',
        'longitude_domain', 'latitude_type', 'edge_model', 'metadata_source',
    }
    if set(context) != required:
        raise GeometryUnresolved(f'Context must have exactly these keys: {sorted(required)}')
    if context['target'] != 'Moon':
        raise GeometryUnresolved('This profile supports the Moon only')
    for key in ('datum', 'frame', 'metadata_source'):
        if not isinstance(context[key], str) or not context[key].strip():
            raise GeometryUnresolved(f'Explicit documented {key} is required')
    radius = context['radius_m']
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius):
        raise GeometryUnresolved('radius_m must be finite and documented')
    if not 1_000_000 < radius < 2_000_000:
        raise GeometryUnresolved('Unsupported lunar radius; Earth defaults are forbidden')
    if context['longitude_direction'] not in ('east', 'west'):
        raise GeometryUnresolved('longitude_direction must be east or west')
    if context['longitude_domain'] not in ('0_360', '-180_180'):
        raise GeometryUnresolved('Unsupported longitude domain')
    if context['latitude_type'] != 'planetocentric':
        raise GeometryUnresolved('Only documented spherical planetocentric input is supported')
    if context['edge_model'] != 'shortest_geodesic':
        raise GeometryUnresolved('Only documented shortest-geodesic footprint edges are supported')


def _one_text(parent, path):
    elements = parent.findall(path)
    if len(elements) != 1 or not (elements[0].text or '').strip():
        raise GeometryUnresolved(f'Missing or ambiguous XML field: {path}')
    return elements[0].text.strip()


def _angle(parent, name, namespace=GEOM):
    nodes = parent.findall(f'{{{namespace}}}{name}')
    if len(nodes) != 1 or nodes[0].get('unit') not in ('deg', 'degree', 'degrees'):
        raise GeometryUnresolved(f'{name} needs one explicit degree-valued field')
    try:
        value = float(nodes[0].text)
    except (TypeError, ValueError) as exc:
        raise GeometryUnresolved(f'Invalid {name}') from exc
    if not math.isfinite(value):
        raise GeometryUnresolved(f'Nonfinite {name}')
    return value


def parse_label(path, context, profile='geom_vertices'):
    """No bbox fallback or guessed corners. Context is a saved, reviewed sidecar."""
    validate_context(context)
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise GeometryUnresolved('Label exceeds the bounded 16 MiB metadata limit')
    root = ET.parse(path).getroot()
    if root.tag != f'{{{PDS}}}Product_Observational':
        raise GeometryUnresolved('Expected a PDS4 Product_Observational label')
    product_id = _one_text(root, f'{{{PDS}}}Identification_Area/{{{PDS}}}logical_identifier')
    target = _one_text(root, f'.//{{{PDS}}}Target_Identification/{{{PDS}}}name')
    if target.casefold() != 'moon':
        raise GeometryUnresolved('Label target does not identify the Moon')
    if profile not in PROFILES:
        raise GeometryUnresolved('Unknown footprint profile')
    if profile == 'geom_vertices':
        groups = root.findall(f'.//{{{GEOM}}}Footprint_Vertices')
        if len(groups) != 1:
            raise GeometryUnresolved('Expected one supported geom:Footprint_Vertices; inspect product profile')
        raw_vertices = [(_angle(node, 'pixel_longitude'), _angle(node, 'pixel_latitude'))
                        for node in groups[0].findall(f'{{{GEOM}}}Pixel_Intercept')]
    else:
        group_name = {
            'isda_system_corners': 'System_Level_Coordinates',
            'isda_refined_corners': 'Refined_Corner_Coordinates',
            'isda_corrected_corners': 'Corrected_Corner_Coordinates',
        }[profile]
        groups = root.findall(f'.//{{{ISDA}}}Geometry_Parameters/{{{ISDA}}}{group_name}')
        if len(groups) != 1:
            raise GeometryUnresolved(f'Expected one explicit ISDA {group_name}; no fallback between coordinate groups')
        # Traverse the perimeter, not XML field order (which lists lower-left first).
        raw_vertices = [(_angle(groups[0], f'{corner}_longitude', ISDA),
                         _angle(groups[0], f'{corner}_latitude', ISDA))
                        for corner in ('upper_left','upper_right','lower_right','lower_left')]
    vertices = []
    for lon, lat in raw_vertices:
        lo, hi = (0, 360) if context['longitude_domain'] == '0_360' else (-180, 180)
        if not lo <= lon <= hi or not -90 <= lat <= 90:
            raise GeometryUnresolved('Coordinates contradict declared longitude/latitude domain')
        if context['longitude_direction'] == 'west':
            lon = -lon
        lon = (lon + 180) % 360 - 180
        vertices.append((lon, lat))
    if vertices and vertices[0] == vertices[-1]:
        vertices.pop()
    if not 3 <= len(vertices) <= 10000 or len(set(vertices)) != len(vertices):
        raise GeometryUnresolved('Need 3–10000 ordered, distinct polygon vertices')
    return Footprint(product_id, vertices, dict(context), sha256_file(path), path.name, profile)


def _center(vertices):
    vectors = [(math.cos(math.radians(lat)) * math.cos(math.radians(lon)),
                math.cos(math.radians(lat)) * math.sin(math.radians(lon)),
                math.sin(math.radians(lat))) for lon, lat in vertices]
    x, y, z = (sum(v[i] for v in vectors) / len(vectors) for i in range(3))
    if math.sqrt(x*x + y*y + z*z) < 0.9:
        raise GeometryUnresolved('Footprints exceed supported local region')
    return math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))


def _project_polygon(footprint, geod, projector, max_segment_m):
    points = []
    vertices = footprint.vertices
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        _, _, distance = geod.inv(*a, *b)
        count = max(0, math.ceil(distance / max_segment_m) - 1)
        if len(points) + count + 1 > 100000:
            raise GeometryUnresolved('Densified footprint exceeds vertex budget')
        points.append(a)
        if count:
            points.extend(geod.npts(*a, *b, count))
    xs, ys = projector.transform(*zip(*points), errcheck=True)
    polygon = Polygon(zip(xs, ys))
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise GeometryUnresolved(f'Invalid footprint; no automatic repair: {explain_validity(polygon)}')
    return polygon


def intersect_footprints(a, b, max_segment_m=100.0):
    """Intersect supported spherical footprints; result establishes eligibility only."""
    for footprint in (a, b):
        validate_context(footprint.context)
    for key in ('target', 'radius_m', 'datum', 'frame', 'latitude_type', 'edge_model'):
        if a.context[key] != b.context[key]:
            raise GeometryUnresolved(f'Incompatible {key}; no implicit datum/frame conversion')
    if not math.isfinite(max_segment_m) or not 1 <= max_segment_m <= 1000:
        raise GeometryUnresolved('Densification must be 1–1000 metres')
    radius = a.context['radius_m']
    geod = Geod(a=radius, b=radius)
    lon0, lat0 = _center(a.vertices + b.vertices)
    for lon, lat in a.vertices + b.vertices:
        _, _, distance = geod.inv(lon0, lat0, lon, lat)
        if distance / radius > math.radians(20):
            raise GeometryUnresolved('Outside supported 20-degree local projection cap')
    geographic = CRS.from_proj4(f'+proj=longlat +R={radius} +no_defs +type=crs')
    projected = CRS.from_proj4(f'+proj=laea +lat_0={lat0} +lon_0={lon0} +R={radius} +units=m +no_defs +type=crs')
    projector = Transformer.from_crs(geographic, projected, always_xy=True, allow_ballpark=False)
    pa = _project_polygon(a, geod, projector, max_segment_m)
    pb = _project_polygon(b, geod, projector, max_segment_m)
    intersection = pa.intersection(pb)
    area = intersection.area
    return {
        'status': 'ELIGIBLE_FOR_BROWSE' if area > 0 else 'REJECTED (geometry)',
        'reason': 'POSITIVE_POLYGON_INTERSECTION' if area > 0 else 'ZERO_AREA_INTERSECTION',
        'science_download_authorized': False,
        'registration_verified': False,
        'product_ids': [a.product_id, b.product_id],
        'inputs': [dict(label=f.label_name, sha256=f.label_sha256, context=f.context, profile=f.profile,
                        normalized_vertices=f.vertices) for f in (a, b)],
        'intersection_wkt': intersection.wkt,
        'projected_geojson': {'a':mapping(pa),'b':mapping(pb),'intersection':mapping(intersection)},
        'intersection_area_m2': area,
        'footprint_area_m2': {'a': pa.area, 'b': pb.area},
        'overlap_percent': {'of_a': 100 * area / pa.area, 'of_b': 100 * area / pb.area},
        'crs_wkt': projected.to_wkt(),
        'normalized_geographic_crs_wkt': geographic.to_wkt(),
        'projection_center_lon_lat': [lon0, lat0],
        'geometry_method': 'Shapely polygon intersection after spherical geodesic densification and lunar LAEA projection',
        'max_segment_m': max_segment_m,
        'boundary_model': 'shortest_geodesic',
        'local_cap_degrees': 20,
        'numerical_area_threshold_m2': 0,
        'versions': {'shapely': shapely.__version__, 'pyproj': pyproj.__version__, 'proj': pyproj.proj_version_str},
        'limitations': [
            'Footprint eligibility is not image correspondence or camera/DEM validation.',
            'Finite densification approximates curved boundaries; inspect boundary-sensitive slivers at finer segmentation.',
            'Only a documented common spherical datum/frame and the supported PDS4 geom profile are accepted.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label_a', type=Path)
    parser.add_argument('label_b', type=Path)
    parser.add_argument('--context-a', required=True, type=Path)
    parser.add_argument('--context-b', required=True, type=Path)
    parser.add_argument('--profile-a', choices=PROFILES, default='geom_vertices')
    parser.add_argument('--profile-b', choices=PROFILES, default='geom_vertices')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-segment-m', type=float, default=100)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite a saved geometry report')
    try:
        a = parse_label(args.label_a, json.loads(args.context_a.read_text()), args.profile_a)
        b = parse_label(args.label_b, json.loads(args.context_b.read_text()), args.profile_b)
        report = intersect_footprints(a, b, args.max_segment_m)
        code = 0
    except (ValueError, OSError, ET.ParseError, DefusedXmlException, pyproj.exceptions.ProjError) as exc:
        report = {'status': 'UNRESOLVED_GEOMETRY', 'reason': str(exc),
                  'science_download_authorized': False, 'registration_verified': False}
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'report': str(args.output)}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
