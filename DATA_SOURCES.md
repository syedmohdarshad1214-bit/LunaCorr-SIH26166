# Data source and attribution notes

LunaCorr uses Chandrayaan-2 OHRC, TMC-2, and IIRS product metadata, labels, and browse imagery distributed through the Indian Space Science Data Centre (ISSDC) PRADAN and Map Browse services. Product IDs, original source references, and acquisition metadata are retained in `data/manifests/` and the audit artifacts. Source science images and ISIS camera cubes are omitted from this repository because they are very large; users who need to reproduce those runs should obtain the named products directly from ISSDC and follow the source service's current terms.

The Moon overview texture is derived from NASA Lunar Reconnaissance Orbiter / LROC and LOLA visual products. The associated source notes and checksums are included under `site/science-evidence/globe-assets/`. These overview textures are for display and are not used to establish scientific registration accuracy.

The repository contains browse and derivative images for demonstration. Retain this attribution when redistributing them, and confirm current ISSDC/NASA data terms before reuse outside an educational prototype.
