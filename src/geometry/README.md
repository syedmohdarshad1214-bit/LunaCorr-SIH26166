# Footprint module: initial supported scope

This module computes actual Shapely polygon intersections in a shared, explicitly spherical lunar Lambert azimuthal equal-area projection. It does not infer pixel correspondence, perform camera/DEM validation, or authorize science downloads. Original Chandrayaan XML acquisition and real-product validation are pending.

Supported explicit XML profiles:

- `geom_vertices`: ordered PDS4 `geom:Footprint_Vertices/geom:Pixel_Intercept` coordinates.
- `isda_system_corners`: ISDA `Geometry_Parameters/System_Level_Coordinates` corners.
- `isda_refined_corners`: ISDA `Geometry_Parameters/Refined_Corner_Coordinates` corners.

The ISDA field names/namespace were observed in the authenticated PRADAN metadata view for `ch2_ohr_ncp_20260103T1005176450_d_img_d18`. Tests of these profiles use clearly synthetic XML fixtures; they are not acquired source labels or proof of schema-wide support. The caller chooses the profile explicitly. No bbox fallback, automatic corner-group switch, coordinate guessing, or invalid-polygon repair occurs.

Each label needs a saved context JSON with these exact keys:

`target, radius_m, datum, frame, longitude_direction, longitude_domain, latitude_type, edge_model, metadata_source`.

Required supported values: target `Moon`; longitude direction `east` or `west`; longitude domain `0_360` or `-180_180`; latitude type `planetocentric`; edge model `shortest_geodesic`. Radius, datum/frame, and the boundary interpretation must be supported by metadata/documentation, not copied from synthetic tests. Context values must agree between products after longitude normalization. Other datums/latitude models require a future explicit validated conversion; they currently stop as unresolved geometry.

```sh
.venv/bin/python -m src.geometry.footprints \
  data/labels/product_a.xml data/labels/product_b.xml \
  --profile-a isda_system_corners --profile-b isda_system_corners \
  --context-a data/labels/product_a.context.json \
  --context-b data/labels/product_b.context.json \
  --output data/derived/pair_overlap.json
```

The paths above are placeholders, not present products. Reports are created exclusively and never overwrite existing reports. They preserve product logical IDs, label hashes, contexts, normalized vertices, projection WKT, software versions, intersection WKT/area, and both directional overlap percentages.

Only local regions with all vertices within a 20-degree cap around the shared projection center are supported. Geodesic edges are densified to at most 100 m segments by default; the boundary is numerically approximated. Refine segmentation and inspect any boundary-sensitive sliver before browse eligibility is used operationally. The module does not silently generalize to global/unsupported footprints or treat missing conventions as no overlap.

## References used for implementation

- [PDS4 Footprint_Vertices](https://pds.nasa.gov/datastandards/documents/dd/all/current/ch36s38.html) and [Pixel_Intercept](https://pds.nasa.gov/datastandards/documents/dd/all/current/ch36s66.html).
- [PROJ lunar-capable spherical LAEA parameters](https://proj.org/en/stable/operations/projections/laea.html).
- [PyProj Transformer axis-order and error handling](https://pyproj4.github.io/pyproj/dev/api/transformer.html).
- [Shapely transformation documentation](https://shapely.readthedocs.io/en/latest/reference/shapely.transform.html).
