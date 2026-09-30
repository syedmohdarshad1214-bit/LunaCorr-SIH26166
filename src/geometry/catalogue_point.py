"""Find original PRADAN catalogue swaths covering one lunar ground point."""

from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile

from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree
import shapefile


LUNAR_GEO = CRS.from_proj4("+proj=longlat +R=1737400 +type=crs")
LAYERS = {
    "OHRC": ("OHRC", "ohr_r1_r11_shape_ver4/ch2_ohr_raw"),
    "TMC-2": ("TMC2", "tmc2_s1_s14_v1_shape/ch2_tmc_derived_ortho"),
    "IIRS": ("IIRS", "iirs_s1_s12_v2_shape/ch2_iir_cal"),
}


@lru_cache(maxsize=1)
def catalogue_layers(root: Path):
    layers = []
    for sensor, (archive, base) in LAYERS.items():
        with ZipFile(root / f"data/raw/catalogue/{archive}_ShapeFiles.zip") as source:
            for suffix in ("_sp", "_np", ""):
                stem = base + suffix
                reader = shapefile.Reader(shp=source.open(stem + ".shp"),
                                          shx=source.open(stem + ".shx"),
                                          dbf=source.open(stem + ".dbf"))
                geometries, ids = [], []
                for shape, record in zip(reader.iterShapes(), reader.iterRecords()):
                    polygon = Polygon(shape.points)
                    if not polygon.is_valid:
                        polygon = polygon.buffer(0)
                    if not polygon.is_empty:
                        geometries.append(polygon)
                        ids.append(record["PRODUCT_ID"])
                projection = Transformer.from_crs(
                    LUNAR_GEO, CRS.from_wkt(source.read(stem + ".prj").decode()),
                    always_xy=True,
                )
                layers.append((sensor, projection, geometries, ids, STRtree(geometries)))
    return layers


def products_at(root: Path, longitude: float, latitude: float):
    products = {sensor: set() for sensor in LAYERS}
    for sensor, projection, geometries, ids, tree in catalogue_layers(root):
        x, y = projection.transform(longitude, latitude)
        point = Point(x, y)
        for index in tree.query(point):
            if geometries[index].covers(point):
                products[sensor].add(ids[index])
    return {sensor: sorted(ids) for sensor, ids in products.items()}
