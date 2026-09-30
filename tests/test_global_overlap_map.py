"""Check the displayed overlap classes against independent original shapefiles."""

import json
import sys
from zipfile import ZipFile

import cv2
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon

from tests.test_globe_catalogue import LAYERS, ROOT
from src.geometry.catalogue_point import products_at


sys.path.insert(0, str(ROOT / "data/derived/REALPAIR005_candidate_screen"))
from rank_current_tmc import read_layer


ASSETS = ROOT / "data/derived/REALPAIR005_science_v1/globe-assets"
SAMPLES = [(19, 35.9, 6), (10, -25, 4), (30, -85, 7),
           (200, 60, 6), (0, 0, 4), (120, -40, 6)]
BITS = {"OHRC": 1, "TMC-2": 2, "IIRS": 4}


def test_global_overlap_map_matches_original_polygons():
    mask = cv2.imread(str(ASSETS / "global-overlaps.png"), cv2.IMREAD_GRAYSCALE)
    metadata = json.loads((ASSETS / "global-overlaps.json").read_text())
    assert mask.shape == (2048, 4096)
    assert sum(metadata["source_product_counts"].values()) == 5556
    original_bits = {(lon, lat): 0 for lon, lat, _ in SAMPLES}
    lunar = CRS.from_proj4("+proj=longlat +R=1737400 +type=crs")
    for sensor, (archive, base) in LAYERS.items():
        with ZipFile(ROOT / f"data/raw/catalogue/{archive}_ShapeFiles.zip") as z:
            for suffix in ("_sp", "_np", ""):
                rows, source_crs = read_layer(z, base + suffix)
                projector = Transformer.from_crs(lunar, source_crs, always_xy=True)
                for lon, lat, _ in SAMPLES:
                    x, y = projector.transform(lon, lat)
                    if any(polygon.covers(Point(x, y)) for _, polygon in rows):
                        original_bits[(lon, lat)] |= BITS[sensor]
    for lon, lat, expected in SAMPLES:
        assert original_bits[(lon, lat)] == expected
        col = int(lon / 360 * mask.shape[1]) % mask.shape[1]
        row = int((90 - lat) / 180 * mask.shape[0])
        display = expected if expected in (3, 5, 6, 7) else 0
        assert int(mask[row, col]) == display


def test_every_ohrc_product_has_displayed_cross_sensor_outline():
    outlines = json.loads((ASSETS / "global-ohrc-overlaps.json").read_text())["outlines"]
    ohrc_ids = {item["product_id"] for item in json.loads((ASSETS / "globe-footprints.json").read_text())["products"]
                if item["sensor"] == "OHRC"}
    assert {item["product_id"] for item in outlines} == ohrc_ids


def test_clicked_overlap_isolates_original_polygons_at_point():
    products = products_at(ROOT, 25.03, -20.31)
    assert products["OHRC"] == []
    assert len(products["TMC-2"]) == 3
    assert len(products["IIRS"]) == 2
    assert "ch2_tmc_ndn_20200203T1845562233_d_oth_m65" in products["TMC-2"]


def test_displayed_triple_clusters_survive_original_shapefile_check():
    """A raster union can create false tiny triples near longitude seams."""
    mask = cv2.imread(str(ASSETS / "global-triples-validated.png"), cv2.IMREAD_GRAYSCALE)
    clusters = json.loads((ASSETS / "global-triple-display-clusters.json").read_text())
    assert clusters["cluster_count"] == len(clusters["clusters"])
    assert len(clusters["clusters"]) > 2
    for cluster in clusters["clusters"]:
        lon, lat = cluster["center_lon_lat"]
        col = int(lon / 360 * mask.shape[1]) % mask.shape[1]
        row = int((90 - lat) / 180 * mask.shape[0])
        assert mask[row, col] == 7
        original = products_at(ROOT, lon, lat)
        assert all(original.values())
        for sensor, product_id in zip(("OHRC", "TMC-2", "IIRS"), cluster["product_ids"]):
            assert product_id in original[sensor]
        assert cluster["area_km2"] > 0
        assert cluster["rings_lon_lat"]
        assert any(Polygon(ring).covers(Point(lon, lat))
                   for ring in cluster["rings_lon_lat"])


def test_false_global_triples_are_removed_from_display():
    original = cv2.imread(str(ASSETS / "global-overlaps.png"), cv2.IMREAD_GRAYSCALE)
    validated = cv2.imread(str(ASSETS / "global-triples-validated.png"), cv2.IMREAD_GRAYSCALE)
    assert original.shape == validated.shape == (2048, 4096)
    assert (original == 7).sum() == 20383
    assert (validated == 7).sum() == 20117
    # The old display projection created a northern false triple here: IIRS
    # does not cover this location in its original PRADAN shapefile.
    lon, lat = 76.508789, 62.885742
    col = int(lon / 360 * original.shape[1])
    row = int((90 - lat) / 180 * original.shape[0])
    assert original[row, col] == 7
    assert validated[row, col] == 0
