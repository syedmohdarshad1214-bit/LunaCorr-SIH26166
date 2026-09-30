# LunaCorr preprocessing contract

Status: requirements and implementation acceptance criteria; no science reader or preprocessing implementation exists yet. Acquire and verify data before frontend work.

## ROI-only processing

Use the validated intersection polygon for the relevant bridge edge. Convert it to source-image windows using documented image geometry; a footprint polygon alone does not supply a pixel-to-ground mapping. Keep the exact polygon mask within rectangular read windows, excluding pixels outside common support from matching and metrics.

Read and process bounded windows. Any filter halo must be minimal, explicit, and excluded from reported matching support outside the overlap. If a required halo is unavailable, mask the affected filter boundary. A three-instrument result must use common three-way support, not unrelated regions on the two TMC-2 bridge edges.

For IIRS, read only selected bands and required spatial windows. Do not unpack a whole cube or materialize all approximately 256 bands. Inspect PDS4 storage metadata before implementing access: dimensions, axis order/interleave, sample type, byte order, offsets, scaling, and special constants must come from the actual product. Record any storage-block read amplification. If the available packaging cannot support bounded access, report the limitation and seek a suitable access path; do not silently extract the entire cube.

## Sensor operations

| Sensor | Required processing design |
| --- | --- |
| OHRC | Percentile normalization; optional CLAHE; denoise; gradient/ridge/edge maps; multi-scale pyramid. |
| TMC-2 | Optical normalization; structural maps; native and approximately 80 m IIRS-context scales. |
| IIRS | Band-quality screening; selected bands, PCA, or physically meaningful reflectance summaries; robust normalization; structural maps. |

Exclude invalid/special pixels from statistics and carry validity and shadow masks through every operation. Record percentile bounds, denoising settings, optional CLAHE settings, and structural-map parameters. Keep processing variants separate for comparison. A flat or insufficiently supported ROI must produce an explicit insufficient-evidence outcome, not fabricated contrast or features.

## IIRS spectral experiments

Start with a small set of clean, physically meaningful summaries. Select bands using the supplied wavelength metadata, quality information, product calibration, and usable ROI evidence. Record band indexing convention, source wavelengths and units, inclusion/exclusion reasons, and summary formula. Do not invent universally suitable band indices before inspecting products. Only label a summary as reflectance if the source product or documented conversion supports that quantity.

Compare selected-band summaries and PCA as explicit experiments; do not indiscriminately use every band. PCA must use a quality-screened band subset and bounded training samples or streaming statistics from the eligible ROI. Save centering/scaling, fitted components, fitting support, and any random seed. Apply the same fitted basis across windows of that representation; independently fitted per-window bases are not interchangeable.

For each experiment, retain product IDs and hashes, overlap/ROI identity, selected bands, preprocessing parameters, runtime and peak memory, valid/shadow support, spatial coverage, and available registration validation metrics. Compare variants on the same evaluation support. Keep evidence scores uncalibrated until validated; unavailable validation remains unavailable.

## Non-destructive scale ladder

| Sensor | Representations |
| --- | --- |
| OHRC | Native → approximately 5 m context → approximately 80 m context. |
| TMC-2 | Native → approximately 80 m context. |
| IIRS | Native → regional structural representation within supported overlap. |

Use the actual product sampling to choose and record grids; approximate targets are not exact integer resize factors. Preserve native data. Every level is a derived artifact with its own geometry, masks, and provenance. Record the aggregation/anti-aliasing method and effective support when reducing scale. A coordinate mapping back to native pixels does not invert information loss from aggregation.

For every derived representation record:

- Source product, file hashes, selected bands, source ROI window and polygon mask.
- Parent representation, shape, actual pixel scale, pixel-center convention, axis order, and units.
- Explicit mapping to parent/native coordinates and any available lunar ground mapping, including its valid domain and uncertainty.
- Lunar CRS or camera/DEM model references as applicable; do not assume an affine model where source geometry requires another model.
- Resampling/filter parameters, normalization parameters, spectral projection, validity mask, and shadow mask.

The IIRS regional representation must not expand computation to the whole scene by default. If the overlap lacks sufficient structure at IIRS resolution, abstain. Additional OHRC detail and interpolation cannot substitute for missing IIRS evidence.

## Acceptance checks for implementation

- Instrument reader tests demonstrate selected-band and bounded-window access without whole-cube extraction/materialization.
- Results agree across reasonable window sizes within documented numerical tolerance, including filter boundaries and shared spectral/normalization parameters.
- Every pyramid level maps known pixel locations through its recorded transforms correctly, including non-integer sampling factors and ROI offsets.
- Outside-overlap, invalid, and masked pixels do not contribute to matching statistics or spatial coverage.
- Empty, flat, or heavily masked common support produces an explicit insufficient-evidence result.
- Experiments preserve native source bytes and report actual memory use and validation availability.
