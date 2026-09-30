"""Export accepted local controls with native-pixel and map provenance.

This is a post-test bookkeeping step. It does not refit a transform or alter
any frozen matching threshold, source raster, or held-out decision.
"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from osgeo import gdal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJECTION = HERE / "science_roi_aligned_middle"
MATCHES = HERE / "science_roi_aligned_middle_test"
TMC = ROOT / "data/raw/ch2_tmc_ndn_20231101T0125121377_d_oth_d18/data/derived/20231101/ch2_tmc_ndn_20231101T0125121377_d_oth_d18.tif"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bilinear_finite(a, x, y):
    x0, y0 = int(np.floor(x)), int(np.floor(y))
    if x0 < 0 or y0 < 0 or x0 + 1 >= a.shape[1] or y0 + 1 >= a.shape[0]:
        return float("nan")
    fx, fy = x - x0, y - y0
    values = np.asarray([a[y0, x0], a[y0, x0 + 1], a[y0 + 1, x0], a[y0 + 1, x0 + 1]], float)
    weights = np.asarray([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy])
    good = np.isfinite(values)
    return float(np.dot(values[good], weights[good]) / weights[good].sum()) if np.any(good) and weights[good].sum() else float("nan")


def main():
    nav = json.loads((HERE / "tmc_navigation_affine.json").read_text())
    matrix = np.asarray(nav["nominal_to_lola_map_affine_2x2"], float)
    offset = np.asarray(nav["nominal_to_lola_map_translation_m"], float)
    lookup = np.load(PROJECTION / "native_pixel_lookup.npz")
    native_sample_line = lookup["sample_line"]
    ds = gdal.Open(str(TMC))
    gt = ds.GetGeoTransform()
    projection = json.loads((PROJECTION / "projection.json").read_text())
    x0, _, _, y1 = projection["bbox_m"]
    crop_col = round((x0 - gt[0]) / gt[1])
    crop_row = round((gt[3] - y1) / -gt[5])
    if abs(gt[1] - 5) > 1e-9 or abs(gt[5] + 5) > 1e-9:
        raise ValueError("Unexpected TMC native resolution")
    out = {}
    for method in ("SIFT", "AKAZE"):
        input_csv = MATCHES / method / "inliers.csv"
        rows = []
        with input_csv.open(newline="") as handle:
            for match in csv.DictReader(handle):
                sx, sy = float(match["ohrc_projected_x_5m"]), float(match["ohrc_projected_y_5m"])
                tx, ty = float(match["tmc_ortho_x_5m"]), float(match["tmc_ortho_y_5m"])
                tmc_col, tmc_row = crop_col + tx, crop_row + ty
                nominal_xy = np.asarray([gt[0] + (tmc_col + 0.5) * 5, gt[3] - (tmc_row + 0.5) * 5])
                aligned_xy = matrix @ nominal_xy + offset
                rows.append({
                    "match_id": match["match_id"], "descriptor": method,
                    "split": match["split"], "accepted_inlier": match["inlier"],
                    "ohrc_native_sample_1based_approx": bilinear_finite(native_sample_line[:, :, 0], sx, sy),
                    "ohrc_native_line_1based_approx": bilinear_finite(native_sample_line[:, :, 1], sx, sy),
                    "ohrc_working_x_5m_px": sx, "ohrc_working_y_5m_px": sy,
                    "tmc_native_col_0based": tmc_col, "tmc_native_row_0based": tmc_row,
                    "tmc_working_x_5m_px": tx, "tmc_working_y_5m_px": ty,
                    "tmc_nominal_map_x_m": nominal_xy[0], "tmc_nominal_map_y_m": nominal_xy[1],
                    "tmc_asp_lola_aligned_map_x_m_approx": aligned_xy[0],
                    "tmc_asp_lola_aligned_map_y_m_approx": aligned_xy[1],
                    "descriptor_distance": match["descriptor_distance"],
                    "forward_residual_tmc_native_5m_px": match["forward_residual_tmc_5m_px"],
                    "source_shadow_mask_quality": "not_used; see shadow_diagnostic_aligned_middle.json",
                    "absolute_ground_accuracy": "unverified_at_5m",
                })
        destination = MATCHES / method / "control_points.csv"
        with destination.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        accepted = [r for r in rows if r["accepted_inlier"] == "1"]
        missing = sum(not np.isfinite(r["ohrc_native_sample_1based_approx"]) for r in accepted)
        out[method] = {"matches": len(rows), "accepted_controls": len(accepted),
                       "accepted_controls_missing_native_lookup": missing,
                       "control_points_csv_sha256": sha256(destination)}
    (MATCHES / "control_point_provenance.json").write_text(json.dumps({
        "audit_id": "REALPAIR005_ALIGNED_MIDDLE_CONTROL_PROVENANCE_V1",
        "input_native_lookup_sha256": sha256(PROJECTION / "native_pixel_lookup.npz"),
        "input_projection_sha256": sha256(PROJECTION / "projection.json"),
        "input_tmc_science_raster": str(TMC),
        "source_pixel_coordinates": "OHRC interpolated from SPICE/DTM projection lookup; TMC native pixel from original 5 m raster geotransform",
        "ground_coordinate_limit": "ASP/LOLA-aligned local map approximation; 5 m absolute geolocation not validated",
        "results": out,
    }, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
