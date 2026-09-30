# Files needed for the first real pair

Acquire original XML and browse image first for this documented candidate:

- OHRC: `ch2_ohr_nrp_20200827T0030107497_d_img_d18`
- TMC ortho: `ch2_tmc_ndn_20231101T0125121377_d_oth_d18`

The OHRC XML is now present in `data/labels` and hash-linked in the manifest. TMC XML and both browse images for this pair are pending. This is still a candidate, not verified overlap.

Keep the product ID and original filename. Place XML in `data/labels`, PNG/JPG in `data/browse`. When the XML polygon and repeated browse structures agree, acquire the matching OHRC `.img`, TMC ortho `.tif`, and geometry/RPC/DEM/camera ancillary files. Preserve the source ZIP directory structure. Put science files in `data/science`. Do not send passwords or session cookies.

The raw OHRC image needs camera-aware preparation before the GeoTIFF adapter can use it. A raw image plus four footprint corners is insufficient to establish its internal pixel geometry. The separate PDS binary reader can inspect windows but does not orthorectify raw images.

For the IIRS leg, choose a TMC/IIRS pair after checking XML overlap; provide selected-band metadata/wavelengths, original label, browse, science cube and geometry files. A perfect triple is not required.

## Browse review record

Use an exact pair and hashes, e.g. `data/derived/browse_review.json`:

```json
{
  "classification": "BROWSE VERIFIED",
  "product_ids": ["EXACT_SOURCE_PRODUCT_ID", "EXACT_TARGET_PRODUCT_ID"],
  "reviewer": "Actual reviewer name",
  "repeated_structures": "Describe the crater and several surrounding craters/ridges, with consistent spacing and their locations in both browses.",
  "browse_checksums": {
    "data/browse/ACTUAL_SOURCE.png": "ACTUAL_SHA256",
    "data/browse/ACTUAL_TARGET.png": "ACTUAL_SHA256"
  }
}
```

This is a template, not an approved review. Use POSSIBLE or REJECTED unless the evidence supports BROWSE VERIFIED. The preparation adapter requires a verified review.

## Manifest and context

Every product must use the 14-field schema in `data/manifests/products.schema.json`. All acquired files need their own SHA-256. `product_records` in the preparation request is an ordered snapshot of two complete source/target records. The original label ID must match the product record.

Read `src/geometry/README.md` for supported XML profiles and coordinate contexts. Fill missing values from product documentation; do not assume Earth CRS, datum, longitude conventions, or camera geometry. The example request intentionally contains nulls/placeholders so it cannot silently claim verified geometry.
