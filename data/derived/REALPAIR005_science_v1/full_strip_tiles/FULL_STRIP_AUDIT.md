# REALPAIR005 full-OHRC-strip audit

**Decision: ABSTAIN for the whole OHRC–TMC-2 overlap.** SIFT and AKAZE pass the frozen local image gates in **6 of 10** contiguous native-OHRC line tiles. Four tiles fail or lack sufficient camera/DTM support. This does not erase the earlier local correspondence result; it narrows its meaning to the *correspondence-supported portion* of the middle ROI, not every pixel in OHRC lines 42,000–58,000.

The exact products are OHRC `ch2_ohr_nrp_20241117T2033118394_d_img_d18`, TMC-2 ortho `ch2_tmc_ndn_20231101T0125121377_d_oth_d18`, and TMC-2 DTM `ch2_tmc_ndn_20231101T0125121377_d_dtm_d18`. Their source SHA-256 values and PDS4 polygon calculation are in the [local scientific report](../ALIGNED_MIDDLE_SCIENTIFIC_VERIFICATION.md). Official OHRC/TMC label polygons intersect over 80.356 km²; that number is *not* the image-verified area.

Before projecting new tile imagery, [config.json](config.json) fixed ten contiguous intervals covering all **101,074 stored OHRC lines** and the full 1–12,000 sample width. These are equal-line audit units, **not equal-area partitions of the true OHRC/TMC footprint intersection**; 6/10 must not be interpreted as 60% of the overlapping lunar area. Its SHA-256 is `dc0ada70aacc8821fbf96900c214041d17b2078ee72398bcb92453bc7b94de8f`. Every tile used the same SPICE/DTM projection, frozen image-derived pointing prior, SIFT/AKAZE parameters, 0.75 reciprocal ratio, 500 TMC-pixel candidate window, training-only affine RANSAC, 4 native TMC-pixel residual gate, ≥6/40% training support, ≥3/40% held-out support, ≥6/18 occupied cells, ≥15% hull, and ≤3-pixel separately fitted reverse median. No threshold was relaxed after seeing tile results. Outputs are in [summary.json](summary.json), with each tile's projection log, image, masks, candidate/inlier CSVs, transforms, metrics, configs, and manifest in its own folder.

| OHRC native lines | Valid pixels in rectangular working image | SIFT held-out | AKAZE held-out | Fixed-gate result |
|---|---:|---:|---:|---|
| 1–10,107 | 62.3% | 198/274 | 51/81 | **ABSTAIN**: reverse medians 3.14 and 3.26 TMC px exceed 3.0 |
| 10,108–20,214 | 64.6% | 153/215 | 25/41 | **ABSTAIN**: AKAZE reverse median 3.40 px exceeds 3.0 |
| 20,215–30,322 | 67.6% | 148/171 | 45/50 | Both image gates pass locally |
| 30,323–40,429 | unavailable | — | — | **ABSTAIN**: only 557 DTM-supported camera rays, below the fixed 1,000-ray projection minimum |
| 40,430–50,537 | 60.0% | 150/215 | 92/101 | Both image gates pass locally |
| 50,538–60,644 | 62.2% | 0/1 | 0/0 | **ABSTAIN**: only 3 SIFT and 1 AKAZE reciprocal candidates |
| 60,645–70,751 | 62.1% | 54/57 | 28/30 | Both image gates pass locally |
| 70,752–80,859 | 61.9% | 89/115 | 44/48 | Both image gates pass locally |
| 80,860–90,966 | 62.4% | 82/93 | 40/45 | Both image gates pass locally |
| 90,967–101,074 | 61.2% | 184/254 | 93/109 | Both image gates pass locally |

**Why the middle-region success did not transfer to every middle pixel:** the 50,538–60,644 tile is physically shadow dominated. In its valid projected pixels, **87.2% of normalized OHRC** and **98.7% of normalized TMC** intensities are below DN 25. The two science images expose only a thin illuminated strip, and there is almost no common feature support. [This post-hoc diagnostic](shadow_diagnostic.json) was not used to select matches or adjust thresholds. A different normalization or SIFT setting cannot recover terrain structure that neither instrument observed. The adjacent 40,430–50,537 tile carries many of the middle ROI's accepted correspondences, which explains how a larger 42,000–58,000 ROI could pass while its shadowed subsection fails.

The 30,323–40,429 failure is different: only **557 sampled rays** reach supported terrain in the aligned TMC DTM, below the fixed 1,000-ray projection minimum. This may reflect partial overlap, terrain coverage, or camera geometry; the tile was not clipped to the exact intersection, so it is **not proof of a DTM hole inside the true overlap**. The first two tiles contain many plausible matches, but their reverse errors fail the *unchanged* 3-pixel gate. They are diagnostic correspondence evidence, not accepted full-strip control. The nine projected images have about **60–68% valid pixels within their axis-aligned rectangular bounds**. Those bounds include area outside the slanted OHRC swath, so these percentages **must not** be read as DTM coverage of the true overlap. Some tiles overlap development imagery used to choose the pointing prior, so this ten-tile run is also not a new fully blind strip-wide validation.

The shortest defensible path forward is to (1) intersect the projected swath and TMC footprint at pixel level to separate true overlap from outside-footprint area, then resolve any camera/terrain gap *inside* that intersection, (2) seek a complementary illumination view where common terrain is shadowed, and (3) freeze any revised model and validate it on new untouched data. Until these requirements pass, the [full-strip decision](decision.json) stays **ABSTAIN**. Neither a global homography nor interpolation through unobserved regions is accepted as proof.
