# LunaCorr Definition of Done

Acceptance checklist frozen from the user brief. Unchecked means not yet demonstrated; requirements documents and synthetic tests do not satisfy real-data checks.

- [ ] Real end-to-end registration on real data is reproducible.
- [ ] Exact product IDs are visible and stored.
- [ ] Geometry is reproducible from saved metadata and configuration.
- [ ] Tentative candidates are visible.
- [ ] Inliers and outliers are distinguished.
- [ ] The saved transform was actually computed for that run.
- [ ] RMSE and inlier metrics come from that exact run, with grid/units identified.
- [ ] Spatial distribution is reported.
- [ ] Failure reports carry explicit ABSTAIN/rejection reasons.
- [ ] At least one baseline comparison exists.
- [ ] Every result has its manifest and resolved configuration.
- [ ] Synthetic runs are clearly labeled throughout their artifacts and presentation.
- [ ] The demonstration runs offline.
- [ ] Backup video/screenshots exist and reference experiment IDs.
- [ ] Every slide number/claim traces to saved evidence.

Minimum real-data scope remains one real OHRC↔TMC-2 pair and one real TMC-2↔IIRS pair; geographically separate pairs are acceptable. Report actual decisions, including abstentions, rather than manufacturing triple registration.

## Immediate execution order

1. Freeze directory and naming contract; define six ownership slots.
2. Validate/rebuild the manifest from actual discovered products, never dummy entries.
3. Acquire 2–5 candidate packs: catalogue record and XML first, true polygon overlap, browse review, then scoped science data.
4. Implement and test PDS4 footprint parsing and true intersection against the actual product profiles.
5. Produce one reproducible real registration before frontend work.
6. Add and save cross-sensor experiments with all required artifacts.
7. Only then add shadow-awareness, bridge composition, independent cycle checks, and UI polish.

The geometry implementation and candidate acquisition can iterate together: science acquisition cannot bypass the overlap/browse gates while a parser is being developed.
