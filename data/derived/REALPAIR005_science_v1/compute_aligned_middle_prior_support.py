"""Measure frozen camera/terrain candidate support before the fitted affine."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE / "science_roi_aligned_middle_test"
result = {"audit_id": "REALPAIR005_ALIGNED_MIDDLE_PREFIT_SUPPORT_V1",
          "grid": "native TMC-2 ortho 5 m/pixel",
          "gate_px": 4.0,
          "meaning": "Identity-map distance between projected OHRC and TMC tentative match positions, before local affine fit; candidate region already includes the frozen image-derived pointing prior.",
          "methods": {}}
for method in ("SIFT", "AKAZE"):
    path = ROOT / method / "matches.csv"
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    a = np.asarray([[float(r["ohrc_projected_x_5m"]), float(r["ohrc_projected_y_5m"])] for r in rows])
    b = np.asarray([[float(r["tmc_ortho_x_5m"]), float(r["tmc_ortho_y_5m"])] for r in rows])
    distance = np.linalg.norm(a - b, axis=1)
    heldout = np.asarray([r["split"] == "heldout" for r in rows])
    result["methods"][method] = {
        "input_matches_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "all_candidates": len(rows),
        "within_4px_before_local_fit": int((distance <= 4).sum()),
        "median_distance_before_local_fit_px": float(np.median(distance)),
        "heldout_candidates": int(heldout.sum()),
        "heldout_within_4px_before_local_fit": int(((distance <= 4) & heldout).sum()),
    }
(HERE / "aligned_middle_prefit_support.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result["methods"], indent=2))
