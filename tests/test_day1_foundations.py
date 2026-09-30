"""SYNTHETIC geometry/inventory regression tests, never real-data evidence."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.geometry.footprints import Footprint, GeometryUnresolved, intersect_footprints, parse_label
from src.ingest.manifest import sha256_file, validate_inventory


CONTEXT = dict(target='Moon', radius_m=1737400, datum='SYNTHETIC spherical test datum',
               frame='SYNTHETIC body-fixed frame', longitude_direction='east',
               longitude_domain='-180_180', latitude_type='planetocentric',
               edge_model='shortest_geodesic', metadata_source='SYNTHETIC regression fixture; not a product default')


def footprint(points, name='SYNTHETIC'):
    return Footprint(name, points, dict(CONTEXT), '0' * 64, 'synthetic.xml')


def label(points):
    vertices = ''.join(f'<g:Pixel_Intercept><g:pixel_longitude unit="deg">{x}</g:pixel_longitude>'
                       f'<g:pixel_latitude unit="deg">{y}</g:pixel_latitude></g:Pixel_Intercept>' for x,y in points)
    return f'''<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"
      xmlns:g="http://pds.nasa.gov/pds4/geom/v1">
      <!-- SYNTHETIC parser fixture, not an acquired or schema-complete product. -->
      <Identification_Area><logical_identifier>urn:synthetic:fixture</logical_identifier></Identification_Area>
      <Observation_Area><Target_Identification><name>Moon</name></Target_Identification>
      <g:Footprint_Vertices>{vertices}</g:Footprint_Vertices></Observation_Area></Product_Observational>'''


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.a = footprint([(0,0),(.1,0),(.1,.1),(0,.1)])

    def test_identical_is_100_percent_eligibility_only(self):
        report = intersect_footprints(self.a, self.a)
        self.assertAlmostEqual(report['overlap_percent']['of_a'], 100)
        self.assertFalse(report['registration_verified'])
        self.assertFalse(report['science_download_authorized'])

    def test_true_polygons_not_bounding_boxes(self):
        a = footprint([(0,0),(.1,0),(0,.1)])
        b = footprint([(.1,.1),(.1,.07),(.07,.1)])
        self.assertEqual(intersect_footprints(a,b)['status'], 'REJECTED (geometry)')

    def test_positive_overlap_and_directional_denominators(self):
        b = footprint([(.05,0),(.2,0),(.2,.1),(.05,.1)])
        report = intersect_footprints(self.a,b)
        self.assertAlmostEqual(report['overlap_percent']['of_a'], 50, delta=.01)
        self.assertAlmostEqual(report['overlap_percent']['of_b'], 100/3, delta=.01)

    def test_dateline(self):
        a = footprint([(179.9,0),(-179.9,0),(-179.9,.1),(179.9,.1)])
        b = footprint([(179.95,0),(-179.95,0),(-179.95,.1),(179.95,.1)])
        report = intersect_footprints(a,b)
        self.assertGreater(report['overlap_percent']['of_a'], 49)
        self.assertLess(report['overlap_percent']['of_a'], 51)

    def test_pole(self):
        a = footprint([(-135,-89.8),(-45,-89.8),(45,-89.8),(135,-89.8)])
        self.assertAlmostEqual(intersect_footprints(a,a)['overlap_percent']['of_a'], 100)

    def test_bad_polygon_is_unresolved(self):
        bad = footprint([(0,0),(.1,.1),(0,.1),(.1,0)])
        with self.assertRaises(GeometryUnresolved):
            intersect_footprints(self.a, bad)

    def test_mismatched_datum_is_unresolved(self):
        bad = copy.deepcopy(self.a)
        bad.context['datum'] = 'different'
        with self.assertRaises(GeometryUnresolved):
            intersect_footprints(self.a, bad)

    def test_parser_and_west_longitudes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.xml'
            path.write_text(label([(359.9,0),(.1,0),(.1,.1),(359.9,.1)]))
            context = dict(CONTEXT, longitude_direction='west', longitude_domain='0_360')
            result = parse_label(path, context)
            self.assertAlmostEqual(result.vertices[0][0], .1)
            self.assertEqual(result.label_sha256, sha256_file(path))

    def test_bbox_does_not_become_polygon(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.xml'
            path.write_text(label([]).replace('<g:Footprint_Vertices></g:Footprint_Vertices>', '<minimum_latitude>0</minimum_latitude>'))
            with self.assertRaises(GeometryUnresolved):
                parse_label(path, CONTEXT)

    def test_isda_corner_profile_preserves_perimeter(self):
        corners = {'upper_left':(0,.1),'upper_right':(.1,.1),'lower_left':(0,0),'lower_right':(.1,0)}
        fields = ''.join(f'<i:{name}_longitude unit="deg">{x}</i:{name}_longitude><i:{name}_latitude unit="deg">{y}</i:{name}_latitude>' for name,(x,y) in corners.items())
        group = '<i:Geometry_Parameters xmlns:i="https://isda.issdc.gov.in/pds4/isda/v1"><i:System_Level_Coordinates>'+fields+'</i:System_Level_Coordinates></i:Geometry_Parameters>'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.xml'
            path.write_text(label([]).replace('<g:Footprint_Vertices></g:Footprint_Vertices>',group))
            result = parse_label(path, CONTEXT, 'isda_system_corners')
            for actual, expected in zip(result.vertices, [(0,.1),(.1,.1),(.1,0),(0,0)]):
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])
            self.assertEqual(intersect_footprints(result,result)['status'],'ELIGIBLE_FOR_BROWSE')
            with self.assertRaises(GeometryUnresolved):
                parse_label(path, CONTEXT, 'isda_refined_corners')


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(sensor='OHRC', product_id='SYNTHETIC_TEST_ONLY', product_type=None,
                           acquisition_time=None, orbit=None, footprint=None, resolution_m=None,
                           browse_file=None, science_file=None, xml_file=None, checksum={},
                           source='https://example.invalid/synthetic', notes='SYNTHETIC test; pending source fields')

    def test_empty_inventory_is_valid_not_evidence(self):
        self.assertEqual(validate_inventory([]), [])

    def test_duplicate_rejected(self):
        self.assertTrue(validate_inventory([self.record,self.record]))

    def test_modified_file_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'label.xml'
            path.write_text('SYNTHETIC original')
            record = dict(self.record, xml_file='label.xml', checksum={'label.xml':sha256_file(path)})
            self.assertEqual(validate_inventory([record], Path(directory)), [])
            path.write_text('modified')
            self.assertTrue(validate_inventory([record], Path(directory)))

    def test_path_escape_rejected(self):
        record = dict(self.record, checksum={'../outside': '0'*64})
        self.assertTrue(validate_inventory([record]))


if __name__ == '__main__':
    unittest.main()
