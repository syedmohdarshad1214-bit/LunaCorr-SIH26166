# Scientific workbench and reproducibility

Status: requirements only. Frontend implementation remains gated on acquired and verified data. No runnable pipeline, offline package, or benchmark exists yet.

## Workbench pages

| Page | Required content |
| --- | --- |
| DATA | Product IDs, sensor, resolution, acquisition time, dimensions, bands, and links to manifest/source metadata. |
| GEOMETRY | Footprint polygons, intersection geometry, directional overlap percentages, coordinate conventions, pass/fail and unresolved states. |
| PREPROCESS | Raw, normalized, shadow-mask, and structural layers with sensor, selected bands/summary, scale, masks, and transform provenance. |
| MATCH | Tentative candidates, inliers, outliers, per-match residuals, matcher/descriptor provenance, and geometry-bounded search support. |
| REGISTER | Before/after views with blink, swipe, and checkerboard, valid-support masks, and named reference grid. |
| VALIDATE | Inlier count/ratio, RMSE, P90, cycle error, coverage, confidence with calibration status, final decision, reasons, and experiment ID. |

Never label tentative candidates as verified control points. Visual alignment alone is not validation. Unavailable metrics must be visibly unavailable, and every pixel error names its native/working sensor grid. Registration comparisons are labeled with their resampling and supported resolution. Failed/abstained runs retain diagnostic access; unsupported warps must not appear as accepted registration.

Display real versus synthetic evidence provenance throughout the workbench and reports. Explicitly label synthetic runs and backups, including synthetic perturbations of real imagery. Synthetic regression/stress results do not substitute for principal real-data evidence. A cached real experiment remains real evidence presented as replay; a synthetic demonstration remains synthetic regardless of how it is displayed.

## Presentation mode and offline judging

One button should run the complete pipeline on a fixed, locally available, acquired and verified demonstration ROI, targeting approximately 15–25 seconds. Preserve early termination for scientific abstention/rejection. Presentation mode does not weaken decision thresholds or force registration.

Record the hardware, input dimensions, selected bands, algorithm configuration, startup boundaries, per-stage timing, total wall time, and peak memory when benchmarking. Distinguish live computation from cached artifact replay; cached results must never be described as a fresh full-pipeline run. The target is not a measured performance claim.

The judging build must work without network access: package the approved scoped inputs, labels, ancillary geometry needed by the selected configuration, dependencies, optional model weights if actually used, and report assets locally. Verify the demonstrated path with networking disabled. Record the data provenance and applicable distribution terms before assembling the distributable package. Missing optional SPICE/ISIS/ASP or optional matchers must be explicit and must not silently produce equivalent-validation claims.

## Recommended stack

- Python, NumPy, SciPy for core processing.
- OpenCV and scikit-image for CV baselines and structural representations.
- pds4_tools and Rasterio/GDAL for inspected PDS/raster formats and bounded readers.
- Shapely and PyProj for geometry; SPICE, ISIS, and ASP when available and needed.
- FastAPI for the API.
- Filesystem, JSON, and SQLite for storage during the five-day prototype effort. This is not an automatic five-day deletion policy.
- RIFT2 and LightGlue as optional later branches.
- Conda or venv for development; Docker for the offline package.

Resolve compatible versions on the target environment, then record a reproducible environment lock and package/container identity. A list of dependency names is not a tested environment. SQLite may index experiments and reviews; finalized experiment artifacts remain the source of record.

## Immutable experiment folders

Allocate a unique ID for each experiment, following the requested naming pattern:

```text
experiments/
  EXP001_OHRC_TMC/
  EXP002_TMC_IIRS/
  EXP003_OHRC_IIRS/
```

These names are examples, not claims that experiments have run. A direct OHRC–IIRS experiment is conditional on observable evidence; it does not replace the required TMC bridge.

Every finalized experiment contains:

```text
manifest.json
config.json
matches.csv
inliers.csv
transform.json
metrics.json
previews/
overlays/
report.html
```

Write a run into a staging directory and publish its final directory only after artifact checks complete. Never overwrite a finalized experiment; reruns and corrections receive new IDs and reference their predecessors. Guard ID allocation against collisions. Record checksums to detect later changes; enforcement of immutability remains an implementation requirement, not something a naming convention guarantees.

| Artifact | Required content |
| --- | --- |
| `manifest.json` | Experiment ID, real/synthetic evidence provenance, run status/reason, timestamp, product-manifest snapshots, source hashes, ROI and geometry references, code/environment identity, parent experiment references, and artifact checksums. Synthetic runs also record generator, seed, known transform when applicable, and perturbations. Exclude the manifest itself from its internal checksum list to avoid self-reference. |
| `config.json` | Fully resolved preprocessing, band/summary, pyramid, matcher, model, threshold, random-seed, and evaluation settings; reference external models/assets by identity and hash. |
| `matches.csv` | All tentative candidates with per-point provenance and verification state; do not discard outliers. |
| `inliers.csv` | Robust-model inliers with the same stable match IDs; distinguish these from final accepted control points. |
| `transform.json` | Models, directions, native/working frame mappings, support domains, geometry sources, and uncertainty; explicit unavailable status if no model is fitted. |
| `metrics.json` | Per-edge/local-model and relevant aggregate metrics, definitions, populations, grids/units, validation availability, thresholds, timing/memory, and final decision/reasons. |
| `previews/`, `overlays/` | Available diagnostic images with grid, scale, support, and verification labels; record unavailable outputs when stages terminate early. |
| `report.html` | Offline-readable evidence report with local assets, experiment ID, configuration, decision, limitations, and links to the supporting artifacts. |

Rejected or abstained experiments retain the same core artifact files: header-only CSVs when there are no matches and explicit unavailable model/metrics values. Do not invent images, transforms, or metrics to fill terminated stages.

## Slide-claim traceability

Every slide claim must cite an experiment ID and the specific artifact/metric or qualitative evidence supporting it. Maintain a claim index alongside presentation assets with claim text, experiment ID(s), artifact paths, metric keys, and evaluation scope. Claims spanning several runs cite every contributing run. Product specifications and algorithm descriptions may additionally need their original references; an experiment ID does not replace source attribution.

Do not generalize one ROI result into instrument-wide accuracy. Keep experimental results, externally sourced facts, and unmeasured performance targets distinguishable.
