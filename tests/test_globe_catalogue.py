"""The globe search must include every ID in the saved catalogue layers."""

import json
from pathlib import Path
from zipfile import ZipFile

import shapefile


ROOT = Path(__file__).resolve().parents[1]
LAYERS = {
    "OHRC": ("OHRC", "ohr_r1_r11_shape_ver4/ch2_ohr_raw"),
    "TMC-2": ("TMC2", "tmc2_s1_s14_v1_shape/ch2_tmc_derived_ortho"),
    "IIRS": ("IIRS", "iirs_s1_s12_v2_shape/ch2_iir_cal"),
}


def test_export_contains_every_saved_product():
    exported = json.loads((ROOT / "data/derived/REALPAIR005_science_v1/globe-assets/globe-footprints.json").read_text())
    products = exported["products"]
    assert len(products) == len({p["product_id"] for p in products})
    for sensor, (archive, base) in LAYERS.items():
        with ZipFile(ROOT / f"data/raw/catalogue/{archive}_ShapeFiles.zip") as z:
            ids = set()
            for suffix in ("", "_sp", "_np"):
                stem = base + suffix
                reader = shapefile.Reader(shp=z.open(stem + ".shp"),
                                          shx=z.open(stem + ".shx"),
                                          dbf=z.open(stem + ".dbf"))
                ids.update(record["PRODUCT_ID"] for record in reader.iterRecords())
        assert ids == {p["product_id"] for p in products if p["sensor"] == sensor}
    assert "ch2_iir_nri_20240422T1522156952_d_img_d18" in {p["product_id"] for p in products}
