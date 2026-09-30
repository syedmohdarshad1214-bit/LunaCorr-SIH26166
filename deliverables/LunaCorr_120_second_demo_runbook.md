# LunaCorr — 2-minute prototype demo

**Story:** A footprint intersection proposes a pair. LunaCorr accepts only a local correspondence that survives camera/terrain and independent image checks, and visibly rejects a convincing false candidate. Keep the globe and evidence panel in one recording. Do not call catalogue triple regions registered.

| Time | On-screen action | Say this |
|---|---|---|
| **0:00–0:15 — Problem** | Start at `http://127.0.0.1:8000/`. Keep the full Moon visible and let it rotate. Point across the top **OHRC → TMC-2 → IIRS** options without clicking them. | “OHRC is our microscope at roughly 25 centimetres per pixel. TMC-2 is the terrain bridge at five metres. IIRS records infrared spectra around eighty metres. Same Moon, three different languages—and an apparent overlap can lie.” |
| **0:15–0:26 — Candidate search** | Click **Triple overlap** in the top bar. Let the gold catalogue rings appear. Click **Pause rotation** so the audited markers stay still. Point briefly to the gold rings, then the green **AUDITED OHRC/TMC** marker near the lower centre. | “These rings are search candidates, not verified registrations. We separate catalogue geometry from evidence on real image pixels.” |
| **0:26–0:41 — Real imagery** | Click the green **AUDITED OHRC/TMC** marker. Wait for the zoom. At the bottom-left of the Moon panel, click **TMC-2 ortho**, then **OHRC browse** to show the two actual products on the globe. | “This is our real OHRC–TMC-2 pair. Here are the actual OHRC browse and TMC ortho images. The science-pixel test is the next step.” |
| **0:41–0:55 — Report** | Click **Scientific verification** above the Moon. Let the Moon slide left and the evidence panel appear. Point to the exact product IDs, **REGISTERED · LOCAL**, and the embedded **AUDIT REPORT**. Scroll *inside the white report pages* just enough to show its table and real-data figure. | “The decision is attached to exact product IDs and a reproducible audit. It says registered only for this middle region—never the whole OHRC strip or absolute ground accuracy.” |
| **0:55–1:14 — Independent matchers** | Move the cursor to the **dark right margin outside the white report** and scroll the evidence panel down to **SIFT / AKAZE**. Show SIFT’s held-out result, then click **AKAZE**. Pause on the numbers and inlier image. | “On frozen held-out locations, SIFT accepts 93 of 111 and AKAZE accepts 48 of 56. Both pass the fixed support and coverage gates. Their relative RMSE is 1.30 and 1.44 pixels on the native five-metre TMC grid—not sub-metre lunar accuracy.” |
| **1:14–1:26 — Visual check** | Click **Terrain swipe**. Drag its slider from the centre to each side once, slowly. | “The swipe lets judges inspect the terrain themselves. The verdict also requires camera and DTM support, spatial spread, reverse checks, and rejected wrong-location controls.” |
| **1:26–1:39 — The trap** | Click **×** at the top-right of the evidence panel, then **Zoom out** above the Moon. Click the pink **REJECTED OHRC/TMC PAIR** marker above the green one. Wait for zoom, then click **Scientific verification**. | “Now try a second pair that looks plausible on the map. LunaCorr challenges it by the same rules.” |
| **1:39–1:54 — Rejection** | Point to **REJECTED · CONSISTENCY** and the embedded two-page report. Scroll *inside the report pages* to its test table, then point to the failed evidence gates below if visible. | “SIFT has zero of six held-out inliers. AKAZE reaches 25 of 50, but covers only 9.3 percent—below the 15 percent gate. Independent terrain alignment disagrees with the image shift. We accept zero control points.” |
| **1:54–2:00 — Impact** | Leave the rejected verdict and report on screen. Do not switch to an untested triple. | “LunaCorr makes every overlap defend its claim—or refuses to register it.” |

## Before recording

1. Open the local prototype in a browser at **1920×1080**, browser zoom **100%**. Use full-screen recording with clear microphone audio. Reload once and confirm the Moon, catalogue, and report images load offline.
2. Rehearse the green and pink marker positions at the current viewport. They are labelled **AUDITED OHRC/TMC** and **REJECTED OHRC/TMC PAIR** after **Triple overlap** is enabled. Keep auto-rotation on for the first 15 seconds, then pause it for reliable clicks.
3. Practice the two different scroll zones: the **white report** scrolls its pages; the **dark panel margin** scrolls down to the matcher tabs. If the report is too small in your capture, click its page to open the full-size PNG, then return to the prototype before continuing.
4. Keep the recorder cursor steady and pause one second after each animation. Rehearse once with a timer; speak at a calm pace. If running long, omit the **Terrain swipe** segment, preserving both decisions and the held-out results.

## Editor cue sheet

Use only short labels, never a number without its grid or scope. Keep each label in the empty part of the frame, away from product IDs and controls.

| Time | Caption to add in editing | Hold on screen |
|---|---|---|
| 0:00 | **FOOTPRINT ≠ PIXEL CORRESPONDENCE** | Full rotating Moon |
| 0:15 | **CATALOGUE CANDIDATES** | Gold overlap rings; no verification claim |
| 0:41 | **REALPAIR005 · REGISTERED LOCAL ROI** | Product IDs, verdict, report |
| 0:55 | **FROZEN HELD-OUT: SIFT 83.8% · AKAZE 85.7%** | Matcher toggle and saved inlier figure |
| 1:39 | **REALPAIR001 · REJECTED CONSISTENCY** | Red verdict, report, failed gates |
| 1:54 | **TRACEABLE YES. TRACEABLE NO.** | Rejected verdict for the final freeze frame |

Export at 1080p or higher with legible UI text and clear narration. Keep the submitted video public or unlisted rather than private. Add your team name and member expertise on a short end card only if the submission format requires it; do not spend demo time on a long team introduction.

## Claim discipline

- **REALPAIR005** is **relative local OHRC↔TMC-2 registration** on the native 5 m TMC ortho grid; full-strip and absolute ground accuracy remain **ABSTAIN**.
- **REALPAIR001** is **REJECTED (consistency)** with zero accepted science control points.
- Gold **Triple overlap** rings are catalogue candidates. The demo does **not** claim a verified OHRC–TMC-2–IIRS triple registration.

The two downloadable audit PDFs and their source links are available inside each pair’s **Scientific verification** panel.

## If a judge asks, “Where is IIRS in the verified result?”

“IIRS is the spectral instrument, around 80 m per pixel with roughly 256 bands. Its footprint candidates are on the globe, but this demo does **not** claim a verified TMC-2-to-IIRS pixel registration. Fine OHRC craters cannot be recovered by simply enlarging IIRS pixels. Our next leg uses geometry-bounded windows and selected clean spectral or structural summaries through TMC-2. Until that leg passes independent image and geometry checks, LunaCorr says **ABSTAIN**.”
