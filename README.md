# LunaCorr — Chandrayaan-2 cross-sensor evidence workbench

**Live prototype:** [lunacorr-sih-demo.pages.dev](https://lunacorr-sih-demo.pages.dev/)

LunaCorr screens lunar product footprints, visualizes candidate overlap regions, and presents saved evidence for a scoped OHRC–TMC-2 registration. It keeps footprint intersection separate from pixel registration and reports where the evidence supports only a local result.

## What is in this repository

- `site/` — the static judge demo, including the Moon explorer, product footprints, frozen evidence views, and report downloads.
- `api/`, `src/`, `frontend/`, `tests/`, and `experiments/` — FastAPI service, geometry/matching pipeline, interface source, tests, and saved baseline experiments. Synthetic experiments are identified in their manifests.
- `evidence/` — selected REALPAIR005 and REALPAIR001 audit records, correspondence tables, metrics, previews, and reports.
- `data/manifests/`, `data/labels/`, and `data/browse/` — product manifests, PDS4 labels, and browse images used by the project.
- `deliverables/` — the SIH technical approach slide, preview, and two-minute demonstration runbook.
- `docs/` — the system, preprocessing, matching, and workbench specifications.

## Scientific scope

REALPAIR005 supports a **local relative OHRC ↔ TMC-2 registration** on the 5 m TMC-2 working grid for the audited middle region. SIFT and AKAZE results, held-out correspondences, reverse closure, spatial coverage, and comparison controls are preserved in `evidence/REALPAIR005/` and displayed in the site.

The full OHRC strip and absolute 5 m ground accuracy remain **ABSTAIN**. IIRS is shown as a catalogue-footprint intersection and has not been registered at pixel level in this evidence. The highlighted global triple regions are catalogue geometry, not proof of three-instrument pixel correspondence. REALPAIR001 is the rejected comparison case. These boundaries are also shown in the live prototype.

## Run the local API workbench

Python 3.12 is the tested runtime. Install the runtime dependencies, then start the app:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.lock.txt
.venv/bin/python serve.py
```

Open `http://127.0.0.1:8000`. The static snapshot under `site/` is included for inspection; the public Cloudflare URL above is the ready-to-use judge demo.

Raw OHRC/TMC-2 science files, full image cubes, camera-model outputs, DEMs, and installed Conda/ASP toolchains are not stored in this repository. They are multi-gigabyte local inputs and are not required to explore the hosted static demo. Their product IDs, source links, and checksums are recorded in the audit materials and manifests where available. Re-running the science pipeline requires obtaining the source products and setting up the documented geometry tools.

## SIH deliverables

- Technical approach slide: `deliverables/LunaCorr_Technical_Approach_PRIMARY.pptx`
- Judge runbook: `deliverables/LunaCorr_120_second_demo_runbook.md`
- Registered and rejected scientific reports: `deliverables/reports/`

## Data sources and reuse

See [`DATA_SOURCES.md`](DATA_SOURCES.md) for attribution and source notes. No software license has been selected for this project yet; until one is added, do not assume the source code is licensed for reuse.
