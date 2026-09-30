# REALPAIR005 code extension and checksum lineage

The original local-image audit artifacts and measurements are unchanged. To run a fixed ten-tile full-strip audit, `project_aligned_candidate.py` was extended with an explicit native-line interval and full sample-width option. Its SHA-256 changed from `7fb3bce8f9181fa1d41e951f36e9b55e55d600a311026089325470596db95844` to `1a77bf48479eda58af25dd82dfde733d9c816e476f20dad33af387a71a811851`. The prior `aligned_middle_sha256.txt` remains untouched as historical evidence and consequently fails on this single source-code file. All other entries in it still match.

`aligned_middle_sha256_v2.txt` validates the current working tree against the original local artifact hashes and the amended source-code hash. The separate [full-strip audit](full_strip_tiles/FULL_STRIP_AUDIT.md) records the new results and decision. This amendment does not re-run or reclassify the earlier local measurements.
