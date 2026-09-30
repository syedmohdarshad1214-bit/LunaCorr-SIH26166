# LunaCorr five-day execution plan

Status: user-supplied delivery plan, not completed work. Day numbers are relative project days; no calendar start date has been assigned. Current workspace contains requirements and directory scaffolding, no acquired products or runnable registration.

## Day 1 — Data + Basic Real Registration

| Workstream | Deliverable |
| --- | --- |
| Data lead | Real candidate inventory with all required manifest fields, source provenance, labels, scoped browse reviews, and gated science acquisition. |
| Geometry lead | Parsing of inspected PDS4/XML footprints, coordinate normalization, shared lunar projection, true polygon intersection, directional overlap percentages, and zero-overlap stop. |
| CV lead | On one real compatible pair: SIFT → matching → ratio filter → RANSAC → validated warp. Process overlap only and preserve geometry-bounded search and native-coordinate transforms. |

Choose a compatible real pair that can establish the end-to-end baseline promptly. Document its sensors and product types; a same-sensor demonstration, if used, does not establish cross-sensor performance. Data and geometry gates apply before the image pipeline.

Save inputs and hashes, configuration, tentative matches, inliers/outliers and residuals, transform, output warp, masks, metrics, previews, and offline report in the experiment format. A second execution from saved inputs/configuration must reproduce the result within declared numerical tolerances and receive a new experiment ID linked to the first.

**Exit criterion:** a reproducible real registration exists by Day 1 night. If unmet, stop decorative work and resolve acquisition, geometry, reading, matching, or validation failures. A plausible overlay, synthetic example, or forced REGISTERED label does not satisfy this gate.

## Day 2 — Cross-Sensor Evidence

Use real OHRC↔TMC-2 and TMC-2↔IIRS pairs. Add explicit scale pyramids, geometry-bounded per-feature search, selected IIRS bands/summaries and bounded PCA experiments. Run SIFT, AKAZE, and structural/RIFT2 variants; record which algorithms actually ran and preserve every experiment.

The minimum evidence target is one real pair for each leg; different geographic regions are acceptable. Do not wait for a perfect triple. Pursue a common-region bridge as the strong target, and a real three-way region with an independent direct OHRC↔IIRS candidate and cycle verification as the best target. Preserve the distinction between having evaluated a real pair and successfully registering it.

**Exit criterion:** real cross-sensor evidence exists for both bridge legs, with explicit results even if a leg abstains or performs weakly. A weak or abstained leg must not be hidden by success on the other edge or claimed as a successful three-instrument registration.

## Day 3 — Differentiators

Add shadow/low-SNR masks, TMC-2 bridge composition, independently supported cycle checks, and spatial-coverage metrics.

Run and tabulate the cumulative ablation ladder:

1. Baseline.
2. + geometry.
3. + structural representation.
4. + shadow masking.
5. + TMC bridge.
6. + cycle consistency.

The mandatory acquisition/true-overlap gate applies to every run. The “+ geometry” ablation measures added matching priors/constraints, not removal of that safety gate. If an experimental baseline deliberately disables bounded feature search, label it as an offline ablation over already eligible ROIs; it is not the production matching policy.

Also compare SIFT, AKAZE, RIFT2/structural, and the full LunaCorr pipeline. A generic structural implementation must not be labeled RIFT2. For bridge ablations, state whether the run uses direct OHRC–IIRS matching or two-leg composition and compare only common evaluation support. Preserve abstentions as outcomes, not missing rows.

The comparison table must include experiment IDs, pair/ROI identity, matcher/representation, enabled components, candidate/inlier counts and ratio, residual/RMSE/P90 definitions and units, coverage, cycle error availability, ground-error provenance, decision/reason, runtime, and peak memory. Compare matched evaluation sets and report the fraction of cases registered/abstained/rejected as well as errors on accepted cases, so selective abstention does not conceal difficulty.

**Exit criterion:** saved differentiator experiments and traceable baseline/ablation tables, including failures and unavailable checks without invented metrics.

## Day 4 — Productization + Validation

After the data and evidence gates, implement DATA, GEOMETRY, PREPROCESS, MATCH, REGISTER, and VALIDATE screens. Add opacity control, correspondence visualization, inlier/outlier switching, downloadable reports, and offline presentation packaging.

Support cached real-result presentation for reliability. Clearly distinguish cached replay from a live pipeline execution; report compute timing from the linked experiment rather than calling replay latency full-pipeline runtime. Keep the approximately 15–25 second live-run target as a separately measured requirement.

**Exit criterion:** usable offline workbench and presentation build that expose provenance, uncertainty, unavailable checks, and correct scientific decisions, with reports traceable to real experiments.

## Day 5 — Judge-Proofing

No new features after lunch. Run the demonstration from a clean start at least ten times and log every attempt, including failures. Define clean start in the run log: new application process, known inputs/configuration, no undeclared warmed process state, and networking disabled for offline checks. Declare whether each attempt is live computation or cached presentation; replay checks do not establish live-compute reliability.

Prepare real success, failure, and difficult cases; the baseline/ablation table; and backup video/screenshots labeled with experiment IDs. Include no-overlap, insufficient/common-structure, shadow, clustering, and inconsistency examples when supported by actual acquired cases. Synthetic data may supply known-transform regression tests, illumination/shadow stress tests, or a UI/demo backup, always explicitly labeled. Synthetic success never substitutes for the principal real-data evidence.

Freeze code identity, environment/package identity, input manifests and hashes, parameters, experiment results, and presentation assets. Corrections require a new version/experiment identity and revalidation rather than edits to frozen evidence.

Run hostile Q&A covering scale limits, common physical support, ground truth, relief models, shadow robustness, independent cycle evidence, clustered controls, uncertainty/calibration, abstention, runtime/memory scope, offline replay, and claim traceability.

**Exit criterion:** at least ten documented clean-start attempts, diagnosed/resolved critical failures, frozen reproducible assets, traceable claims, and usable backups. If an actual success case or another gate is missing, report that gap; do not relabel a failure to satisfy the schedule.

## Current gate and next work

- Day 1 has started: the structure/checklist are frozen, six interim responsibility slots are documented, and manifest/geometry groundwork is implemented with synthetic regression tests.
- Authenticated PRADAN/map access is established. Five real catalogue candidates and four proposed pair packs are stored; no original XML, browse, or science files have been acquired yet.
- Next dependency: retrieve original PDS4 labels and supporting coordinate conventions, validate the real product profiles, and complete polygon/browse gates before scoped science acquisition. The map catalogue's product-details popup is not currently appearing through browser control; user-assisted opening is pending.
- Then implement and reproduce the basic real-pair pipeline. Frontend/decorative work stays deferred until the evidence milestones permit it.

Workstream labels describe responsibilities; no people or autonomous agents have been assigned by this document.
