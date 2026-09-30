# REALPAIR001 adjusted-camera scientific verification

**Audit ID:** `REALPAIR001_adjusted_registration_v5`  
**Products:** OHRC `ch2_ohr_nrp_20200827T0030107497_d_img_d18`; TMC-2 ortho `ch2_tmc_ndn_20231101T0125121377_d_oth_d18`; TMC-2 DTM `ch2_tmc_ndn_20231101T0125121377_d_dtm_d18`  
**Decision:** **REJECTED (consistency)**  
**Accepted science control points:** **0**

## Findings

| Test | Evidence | Result |
|---|---:|---|
| ISIS↔CSM camera equivalence | Maximum round-trip difference 0.01398 OHRC px | PASS |
| OHRC stereo bundle adjustment | 10,690 final points; median residuals 0.2576/0.2626 OHRC px | PASS |
| Adjusted OHRC→TMC DTM projection | Real DTM, 5 m grid, 2,373 × 5,149 pixels | PASS |
| Fresh SIFT gradient support | Train 8/19 (42.1%); held out 0/6 (0%); 5/18 cells | FAIL |
| Fresh AKAZE gradient support | Train 36/85 (42.4%); held out 25/50 (50.0%) | PASS support |
| AKAZE spatial control | 8/18 cells; convex hull 9.3% versus 15% gate | FAIL coverage |
| Independent reverse AKAZE check | Held-out closure RMSE 2.862 native TMC px; P90 4.083 px | Mixed; P90 exceeds 3 px |
| Independent ASP `pc_align` | 10,690 OHRC terrain points against TMC DTM; 649.64 m translation; output RMSE 97.88 m | GEOMETRIC ESTIMATE |
| Geometry/image agreement | Descriptor median displacement 6.97 km versus `pc_align` 0.650 km | FAIL |

## Evidence boundary

The adjusted OHRC camera is internally valid and its stereo pair converges strongly. That validates the camera implementation and relative OHRC geometry. It does not create an absolute tie to TMC-2.

The AKAZE branch passes the fixed training and held-out support ratios on points excluded from earlier development matches, but its inliers occupy too little of the footprint. More decisively, both descriptor branches select terrain about 6.97 km from the camera prediction, while ASP's independent terrain alignment estimates only 0.650 km of translation. The agreement of SIFT and AKAZE near the search prior is therefore insufficient: repeated crater structure can make both descriptors agree on the same wrong region.

The system consequently rejects this candidate for consistency. The ~6.97 km image displacement remains an image-derived hypothesis and is not written into the camera, raster transform, or control-point catalogue.

## Reproducibility

- `config.json` records camera/DEM projection settings and fixed gates.
- `match_config.json` freezes matching, shadow masking, prior exclusion radius, and the fresh spatial partition.
- `EXP038...` and `EXP039...` each contain `config.json`, `matches.csv`, `inliers.csv`, `reverse_matches.csv`, `transform.json`, `metrics.json`, and `manifest.json`.
- `pc_align/` contains the independent ASP transform, before/after error tables, iteration history, and tool log.
- `checksums.sha256` binds the critical camera, projection, matcher, and terrain-alignment artifacts.

## Next scientifically valid action

Do not tune against the failed SIFT held-out points. Select a more illumination-compatible OHRC/TMC pair or introduce an independent lunar control source, then reserve a new untouched spatial region before matcher tuning. This pair remains useful as a documented difficult/rejected case for the LunaCorr demo.
