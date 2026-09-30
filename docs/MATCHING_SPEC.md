# LunaCorr matching and verification contract

Status: captured requirements; no matching engine or thresholds are implemented or validated yet. The acquisition and ROI preprocessing gates remain prerequisites.

## Baselines and bounded search

Build and evaluate in order: **SIFT → AKAZE → RIFT2/phase-structural branch → optional LightGlue reranking**. Preserve baseline results for comparison. RIFT2 and an alternative phase-structural implementation must be named accurately; do not label a generic phase representation as an implemented RIFT2 algorithm. LightGlue is optional and is considered only after robust candidates exist, with descriptor/input compatibility verified.

Each source feature searches only within its geometry-bounded target window. Record the predicted target location, window bounds, geometry source, and uncertainty used to size the window. Intersect search support with the overlap and validity/shadow masks. Do not silently fall back to unrestricted global matching if pixel-level geometry is unavailable. Footprint intersection alone cannot supply per-feature target predictions.

## Robust verification: steps 24–28

These steps elaborate matching and robust fitting within the original 13-stage pipeline.

24. Generate and store tentative matches with descriptor source, match direction, and search-window provenance.
25. Fit a suitable transform robustly using RANSAC or MAGSAC; record the estimator, parameters, random seed, model, and fitting support.
26. Separate inliers and outliers explicitly; preserve outliers and rejection reasons for diagnosis.
27. Store per-match residuals with their definition, evaluation frame/grid, and units. Separate fitting residuals from held-out or independent camera/DEM validation residuals.
28. Expose verification state explicitly. Tentative matches are never verified control points. Robust-model inliers remain distinguishable from points that have passed the additional consistency, mask, coverage, and geometry checks.

## Transformation selection

Consider translation, similarity, affine, and homography, choosing the simplest model supported by local terrain and validation residuals. Do not promote complexity merely because fitting error decreases. Check model degeneracy, spatial support, validation residuals, and the domain where the model is supported.

Prefer local/tiled or camera-aware models on rough terrain. Record tile boundaries and model domains, and assess compatibility across neighboring local models. Never extrapolate a small supported crater region into claimed control of the whole overlap.

## TMC-2 bridge and per-point provenance

Run OHRC→TMC-2 and TMC-2→IIRS separately for forward composition. This uses the same two physical edges as the TMC-centered OHRC→TMC-2←IIRS topology; record estimation and application directions explicitly. Reverse estimates used as independent evidence are separate matching runs, not algebraic inversions relabeled as new evidence.

Infer OHRC↔IIRS only where both legs have reliable support through the common TMC frame. Preserve native and working-grid coordinates, and the available ground mapping. Do not join two unrelated TMC features simply because they share an image; record the common TMC location, association tolerance, model support, and propagated uncertainty.

For every correspondence store:

- Product IDs, source hashes, pair/run IDs, tile/local-model IDs, and tentative/inlier/outlier/final verification state.
- OHRC native pixels, TMC-2 native pixels, and IIRS native pixels when available, including axis order and pixel-center convention.
- Working-grid coordinates and explicit mappings to native coordinates for each observation.
- Ground coordinate, units, lunar CRS/datum, mapping source, and uncertainty when available; otherwise null with a reason.
- Descriptor/structural representation source and parameters, selected IIRS bands or summary identity, and geometry search window.
- Per-leg residuals, independent validation residuals if available, and cycle errors with coordinate frames and units.
- Mask quality and valid/shadow support, confidence/evidence score with calibration status, and rejection/abstention reasons.
- Whether each coordinate is observed, independently matched, or inferred through a transform. An inferred IIRS coordinate is not a separately observed IIRS control point.

## Cycle consistency

When an independently obtained direct OHRC→IIRS candidate exists at an observable common scale, compare it with OHRC→TMC-2→IIRS in the same endpoint frame. Preserve direct and composed evidence separately.

Otherwise, traverse forward and back using independently estimated reverse matches/models and measure return error. A transform followed by its exact algebraic inverse is not an evidence-bearing cycle test. Record the cycle path, independent observations, source/endpoint grid, valid support, and sensor-aware threshold. Forward/back consistency is a weaker check than an independently observed three-instrument loop and does not by itself establish ground accuracy.

Reject or downgrade individual candidates exceeding the applicable cycle threshold. For the run-level policy supplied below, high cycle error yields ABSTAIN_INCONSISTENT_CYCLE. If no independent cycle can be evaluated, report unavailable rather than a zero error or passed check; missing required evidence cannot fall through to REGISTERED.

## Spatial distribution

Grid the overlap region and report occupied eligible cells, the eligible-cell denominator, and occupancy fraction. Record grid origin, dimensions, physical cell size, and eligibility mask. Also report inlier convex-hull coverage relative to the overlap, clipped to the overlap, and an explicitly defined clustering measure. Include coverage relative to usable support as a separate quantity if masks reduce the region.

Report distribution per edge and local model, and over common support for three-instrument results. Dense matches in one crater do not establish control over the whole ROI. Degenerate point sets must not produce misleading hull coverage.

## Required metrics

| Metric | Required interpretation |
| --- | --- |
| Candidate count | Count of tentative correspondences entering robust fitting for the named edge/tile. |
| Inlier count / ratio | Accepted robust-fit inliers and ratio to the stated candidate count; zero denominator is unavailable. |
| Mean / median residual | Residual definition, population, grid, and units. |
| RMSE | For 2D positional residual vectors, square root of mean squared vector norm; distinguish fitting and independent validation populations. |
| P90 error | 90th percentile of the named positional-error population, with units and percentile convention. |
| Spatial coverage | Grid occupancy, hull coverage, and clustering with definitions and denominators. |
| Cycle closure error | Path, independent support, endpoint frame, population summary, and threshold. |
| Ground error (m) | Ground-frame error definition and mapping/reference provenance; distinguish ground-projected internal residual from independently measured absolute accuracy. |
| Runtime / memory | Per-stage and total elapsed time, peak-memory measurement method, and processing scope. |

Every pixel error must identify sensor and native/working grid, including its actual scale. Small residuals on an upsampled IIRS grid do not establish sub-metre lunar accuracy. Unknown metrics stay null/unavailable, never zero. Report both bridge edges separately rather than allowing aggregate metrics to hide a weak edge.

## Ordered abstention policy

The user's policy, preserved in order:

```yaml
if no_true_overlap: REJECT_GEOMETRY
elif too_shadowed: ABSTAIN_SHADOW
elif too_few_candidates: ABSTAIN_INSUFFICIENT_FEATURES
elif poor_inlier_ratio: ABSTAIN_GEOMETRY
elif poor_spatial_coverage: ABSTAIN_CLUSTERED_MATCHES
elif high_cycle_error: ABSTAIN_INCONSISTENT_CYCLE
else: REGISTERED
```

`REJECT_GEOMETRY` maps to the public status REJECTED (geometry). Every `ABSTAIN_*` value maps to ABSTAIN and is retained as its reason code. REJECTED (consistency) remains in the public vocabulary, but this ordered automatic policy does not currently emit it; do not invent an additional automatic rejection threshold.

Apply the policy only after required evidence is available and the geometry/model/residual validation prerequisites pass. A missing metric is not a false predicate. REGISTERED still requires geometry and image evidence to agree under the overall decision contract, including acceptable residuals; the final `else` is not permission to skip those prerequisites. Record the first terminating reason and any other evaluated failures.

Define shadow, candidate-count, inlier-ratio, coverage, residual, and sensor-aware cycle thresholds using explicit configurations and validation data. No threshold values, calibrated confidence claims, or accuracy guarantees are established by this document. Apply acceptance checks independently to both bridge legs before reporting three-instrument registration.
