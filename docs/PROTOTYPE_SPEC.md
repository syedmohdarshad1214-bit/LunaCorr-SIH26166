# LunaCorr prototype baseline

Status: requirements captured from the project brief; no registration implementation or real-data validation yet.

The application root is `lunacorr/` within this workspace. See its [README](lunacorr/README.md) and the [workbench/reproducibility contract](WORKBENCH_SPEC.md) for the requested structure, offline demonstration target, and experiment artifacts.

Follow the [five-day execution plan](EXECUTION_PLAN.md). The Day 1 gate is a reproducible real registration, followed by cross-sensor evidence, differentiator experiments, productization, and a frozen judging build.

**Implementation order: acquire and verify data before frontend work.** Follow [the acquisition contract](lunacorr/data/README.md). Every discovered product needs a manifest entry, including products later rejected. Science downloads require positive polygon overlap and a BROWSE VERIFIED review. Catalogue proximity alone never authorizes bulk downloads.

## Objective

Identify physically corresponding lunar locations across Chandrayaan-2 OHRC, TMC-2, and IIRS. Approximate instrument characteristics supplied in the brief:

| Instrument | Ground sampling | Role |
| --- | --- | --- |
| OHRC | 0.25–0.30 m/px | Fine optical imagery |
| TMC-2 | 5 m/px | Intermediate scale and geometry bridge |
| IIRS | 80 m/px, approximately 256 bands | Hyperspectral imagery |

Required topology: **OHRC → TMC-2 ← IIRS**. Both edges must independently pass geometry and image-evidence checks before a three-instrument registration can be accepted. A successful edge may be reported separately if the other edge cannot be accepted.

The OHRC-to-IIRS sampling gap is approximately 320× at 0.25 m/px. Upsampling does not create separable fine detail in IIRS. Evaluate correspondence at supported physical scales and report uncertainty in lunar ground units as well as explicitly named image-pixel units.

### Real-data evidence targets

| Level | Required evidence |
| --- | --- |
| Minimum acceptable | One real OHRC↔TMC-2 pair and one real TMC-2↔IIRS pair, each independently evaluated with saved validation evidence. The pairs may be from different regions. |
| Strong | Both legs from the same geographic region with common supported locations, forming a reliable OHRC→TMC-2→IIRS bridge. |
| Best | A real three-way region plus an independently obtained direct OHRC↔IIRS candidate and an evaluated cycle check. Report whether the check passes; availability alone does not establish REGISTERED. |

Do not delay pairwise acquisition or validation while searching for a perfect triple overlap. Pairwise results from different regions remain pairwise results; they cannot be composed into a claimed three-instrument correspondence. Report achieved evidence level alongside each pair's actual scientific decision. An abstained real-data experiment is useful evidence, but must not be described as a successful registration.

### Synthetic-data role

Use synthetic data for known-transform regression ground truth, illumination/shadow stress tests, and explicitly labeled UI/demo backups. Synthetic success never substitutes for principal real-data evidence or advances the real-data evidence tier.

Label every synthetic run in its experiment manifest, report, previews/overlays, workbench presentation, and slide claims. Record generator/configuration/seed, source inputs, known transform where applicable, and applied perturbations. Real imagery modified with a synthetic warp or illumination change is a synthetic test for those modifications; retain its real source provenance. Keep synthetic and unmodified real-data evaluation results distinguishable in comparisons.

## Decision contract

| Status | Meaning |
| --- | --- |
| REGISTERED | Geometry and observable image evidence agree, and required validation checks pass. |
| ABSTAIN | Evidence is insufficient to establish correspondence, including insufficient common structure or excessive shadowing. |
| REJECTED (geometry) | Validated geometry establishes that there is no true overlap. |
| REJECTED (consistency) | Explicit rejection of geometrically or cycle-inconsistent candidates. The current automatic run policy below conservatively abstains on poor inlier ratio or high cycle error. |

Catalogue proximity and footprint intersection establish candidate eligibility only. Neither proves pixel correspondence. Missing or unreliable geometry is insufficient evidence, not proof of no overlap. Abstention is a designed outcome.

Each result must include the status, reason codes, per-edge evidence, validation availability, uncertainty, and data provenance. Do not collapse unavailable checks into successful checks. Invalid inputs and runtime errors must remain distinguishable from scientific decisions.

The latest [matching and verification contract](MATCHING_SPEC.md) specifies baseline order, per-match provenance, metric units, and the user's ordered abstention rules. Under those rules, high cycle error yields ABSTAIN with reason ABSTAIN_INCONSISTENT_CYCLE; do not silently relabel that run REJECTED (consistency).

## Required 13-stage pipeline

1. **PDS4 metadata:** ingest product labels and associated coordinate/camera information; expose missing prerequisites.
2. **Footprint overlap:** assess geometric eligibility and document the geometry source and its limitations.
3. **ROI extraction:** extract corresponding candidate regions while preserving spatial transforms and validity masks.
4. **Sensor preprocessing:** apply instrument-appropriate handling of valid pixels, radiometry, and spectral data; record operations.
5. **Multi-scale pyramids:** construct representations at meaningful physical scales for each bridge edge; avoid treating interpolation as recovered detail.
6. **Shadow masking:** mask or down-weight shadow-dominated observations; assess usable support.
7. **Structural representations:** derive and inspect gradient, phase-congruency, or ridge representations; select implemented methods explicitly.
8. **Matching:** generate candidates independently for OHRC–TMC-2 and IIRS–TMC-2 using structural evidence.
9. **RANSAC/MAGSAC:** estimate and validate suitable local geometric models; identify which estimator actually ran.
10. **Cycle consistency:** evaluate independently supported cross-instrument or local cycles where available; otherwise report unavailable.
11. **Spatial coverage:** measure the distribution of valid support across the ROI, including support per local model.
12. **RMSE/confidence:** report residual definitions, coordinate units, validation support, uncertainty, and decision thresholds. Treat confidence as an uncalibrated evidence score until calibrated against validation data.
13. **Decision:** emit one of the four statuses with supporting evidence. Earlier stages may terminate with a justified decision.

### ROI processing and scale ladder

Process only geometrically overlapping ROIs. Read selected IIRS bands by spatial window; never unpack or load a whole cube as the default processing path. The detailed [preprocessing contract](PREPROCESSING_SPEC.md) defines sensor-specific operations, bounded spectral experiments, and transform provenance.

- OHRC native → approximately 5 m context → approximately 80 m context.
- TMC-2 native → approximately 80 m context.
- IIRS native → regional structural representation.

Preserve native inputs and explicit transforms between every level. These are separate derived representations, never a single destructive resize.

## Physical constraints

### Lunar relief

The brief rules out relying on a global 2D homography as a universal surface model. Plan for PDS4/SPICE geometry, DEM constraints, tile-based local models, and camera/DEM residual checks. Report unavailable camera, SPICE, or DEM inputs explicitly; never label a simple image warp as DEM-validated registration.

### Illumination changes

Use structural representations and shadow masks to address moving shadows and contrast changes. Down-weight shadow-dominated features and abstain when insufficient usable common structure remains. Thresholds need validation rather than assumed universal values.

### Sensor differences

Use structural evidence rather than raw cross-sensor brightness as the primary matching signal. IIRS spectral reduction and band selection must be documented and tied to the supplied product. TMC-2 splits the scale gap into two stages but does not restore fine information absent from IIRS.

## Consistency safeguards

- A transform followed by its algebraic inverse is not independent cycle evidence.
- The two-edge bridge topology alone does not supply an independent three-instrument cycle. Additional observations or constraints are required; record their source.
- Residuals on model-fitting matches alone are insufficient validation. Distinguish fitting residuals from held-out or independent geometry residuals.
- Match count alone is insufficient: evaluate spatial coverage, usable structure, and local-model support.
- Keep synthetic demonstrations explicitly labeled and separate from real-data performance claims.
- Preserve a stage audit trail with inputs, parameters, outputs, skipped checks, and termination reasons.

## Inputs still needed

- Representative OHRC, TMC-2, and IIRS products with PDS4 labels and ancillary files.
- Available SPICE kernels, camera models, DEMs, coordinate conventions, and quality flags.
- Validation correspondences or other independent reference constraints, if available.
- Deployment expectations and demonstration scope.

Do not invent product schemas, accuracy claims, calibrated confidence values, or validation outcomes before inspecting data and testing the implementation.
