"""Project OHRC through ASP-aligned terrain with a frozen pointing *prior*.

This creates candidate imagery, not an accepted camera or ground correction.
"""

import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import spiceypy as spice
from osgeo import gdal, osr
from scipy.interpolate import LinearNDInterpolator

from direct_camera_dtm_screen import (HERE, META, PIXEL_RAD, R_KM,
                                      ray_state, sphere_intersection, lat_lon)

ROOT = HERE.parents[2]
OHRC_ID = "ch2_ohr_nrp_20241117T2033118394_d_img_d18"
TMC_ID = "ch2_tmc_ndn_20231101T0125121377_d_oth_d18"
OHRC = ROOT / "data/raw" / OHRC_ID / "data/raw/20241117" / (OHRC_ID + ".img")
TMC = ROOT / "data/raw" / TMC_ID / "data/derived/20231101" / (TMC_ID + ".tif")
DTM = HERE / "aligned_tmc_local/dtm_navonly.vrt"
NAV = json.loads((HERE / "tmc_navigation_affine.json").read_text())
NAV_A = np.asarray(NAV["nominal_to_lola_map_affine_2x2"], dtype=np.float64)
NAV_B = np.asarray(NAV["nominal_to_lola_map_translation_m"], dtype=np.float64)
NAV_INV = np.linalg.inv(NAV_A)
HEIGHT_PLANE = NAV["vertical_delta_plane_m_from_nominal_xy_m"]["coefficients_x_y_constant"]
# Candidate prior from two earlier development ROIs; frozen before middle imagery.
POINTING_PRIOR_TRUE_XY_M = np.array([-2462.77986511, -4187.92953467])
TILE = os.environ.get("LUNACORR_TILE_LINES")
if TILE:
    TILE_START, TILE_END = map(int, TILE.split(":"))
    if not (1 <= TILE_START <= TILE_END <= 101074 and TILE_END-TILE_START < 12000):
        raise ValueError("Tile lines must be a bounded OHRC native line interval")
ROI_KIND = ("start" if os.environ.get("LUNACORR_ROI_START") == "1" else
            "middle" if os.environ.get("LUNACORR_ROI_MIDDLE") == "1" else
            "final" if os.environ.get("LUNACORR_ROI_FINAL") == "1" else "first")
OUT = (HERE / f"full_strip_tiles/tile_{TILE_START:06d}_{TILE_END:06d}/projection" if TILE else
       HERE / {"start": "science_roi_aligned_start", "first": "science_roi_aligned_first",
               "middle": "science_roi_aligned_middle", "final": "science_roi_aligned_final"}[ROI_KIND])
OUT.mkdir(parents=True, exist_ok=True)


def main():
    spice.furnsh(str(META))
    dtm = gdal.Open(str(DTM))
    dtm_band = dtm.GetRasterBand(1)
    dgt = dtm.GetGeoTransform()
    inv_dgt = gdal.InvGeoTransform(dgt)
    tmc = gdal.Open(str(TMC))
    tgt = tmc.GetGeoTransform()
    src = osr.SpatialReference()
    src.ImportFromProj4("+proj=longlat +a=1737400 +b=1737400 +no_defs")
    dst = osr.SpatialReference(wkt=dtm.GetProjection())
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_map = osr.CoordinateTransformation(src, dst)

    def xy(point):
        lat, lon = lat_lon(point)
        x, y, _ = to_map.TransformPoint(lon, lat)
        return x, y

    def h_at(point):
        x, y = xy(point)
        col, row = gdal.ApplyGeoTransform(inv_dgt, x, y)
        c, r = int(col), int(row)
        if not (0 <= c < dtm.RasterXSize and 0 <= r < dtm.RasterYSize):
            return None
        h = int(dtm_band.ReadAsArray(c,r,1,1)[0,0])
        if h == dtm_band.GetNoDataValue():
            return None
        nominal_xy = NAV_INV @ (np.array([x,y]) - NAV_B)
        return h + HEIGHT_PLANE[0]*nominal_xy[0] + HEIGHT_PLANE[1]*nominal_xy[1] + HEIGHT_PLANE[2]

    map_pts, raw_pts = [], []
    samples = np.r_[np.arange(1, 12001, 250), 12000] if TILE else np.arange(1000, 11001, 250)
    line_start, line_end = ((TILE_START, TILE_END) if TILE else
                            {"start": (1000, 9000), "first": (10000, 40000), "middle": (42000, 58000),
                             "final": (60000, 90000)}[ROI_KIND])
    lines = np.arange(line_start, line_end+1, 100)
    for line in lines:
        _, _, pos, _, _ = ray_state(int(line))
        et = spice.utc2et(ray_state(int(line))[0])
        rotation = spice.pxform("J2000", "IAU_MOON", et) @ spice.pxform("CH2_OHRC", "J2000", et)
        for sample in samples:
            camera = np.array([1.0, 0.5*PIXEL_RAD, (6000.5-sample)*PIXEL_RAD])
            camera /= np.linalg.norm(camera)
            ray = rotation @ camera
            ground = sphere_intersection(pos, ray, R_KM)
            h = h_at(ground)
            if h is None:
                continue
            for _ in range(4):
                ground = sphere_intersection(pos, ray, R_KM+h/1000)
                nxt = h_at(ground)
                if nxt is None:
                    break
                h = nxt
            if nxt is None:
                continue
            # Keep the output on native TMC nominal pixels; its ASP alignment is
            # used to sample real terrain. The pointing shift is only a prior.
            true_xy = np.asarray(xy(ground)) + POINTING_PRIOR_TRUE_XY_M
            map_pts.append(NAV_INV @ (true_xy - NAV_B))
            raw_pts.append((int(sample), int(line)))
    map_pts = np.asarray(map_pts)
    raw_pts = np.asarray(raw_pts)
    if len(map_pts) < 1000:
        raise RuntimeError(f"Insufficient DTM-supported grid: {len(map_pts)}")
    # Trim only the outer geometry grid; NaN interpolation retains nodata holes.
    edge = (np.min, np.max) if TILE else (lambda a: np.percentile(a,1), lambda a: np.percentile(a,99))
    x0 = np.floor(edge[0](map_pts[:,0])/5)*5
    x1 = np.ceil(edge[1](map_pts[:,0])/5)*5
    y0 = np.floor(edge[0](map_pts[:,1])/5)*5
    y1 = np.ceil(edge[1](map_pts[:,1])/5)*5
    nx, ny = int((x1-x0)/5), int((y1-y0)/5)
    if nx*ny > 2_500_000:
        raise RuntimeError(f"ROI too large: {nx}x{ny}")
    gx = x0+(np.arange(nx)+0.5)*5
    gy = y1-(np.arange(ny)+0.5)*5
    xx, yy = np.meshgrid(gx, gy)
    interp = LinearNDInterpolator(map_pts, raw_pts, fill_value=np.nan)
    coords = interp(xx, yy).astype(np.float32)
    valid = np.isfinite(coords[:,:,0]) & np.isfinite(coords[:,:,1])
    # Preserve every output pixel's native OHRC sample/line for point provenance.
    np.savez_compressed(OUT/"native_pixel_lookup.npz", sample_line=coords, valid=valid)
    # A contiguous 10,000 x 30,000 source crop is reduced with INTER_AREA.
    raw = np.memmap(OHRC, dtype=np.uint8, mode="r", shape=(101074,12000))
    s0, s1, l0, l1 = (0, 12000, line_start-1, line_end) if TILE else (999, 11000, line_start-1, line_end)
    low = cv2.resize(np.asarray(raw[l0:l1, s0:s1]), ((s1-s0)//20,(l1-l0)//20), interpolation=cv2.INTER_AREA)
    u = (coords[:,:,0]-1-s0) * (low.shape[1]/(s1-s0))
    v = (coords[:,:,1]-1-l0) * (low.shape[0]/(l1-l0))
    projected = cv2.remap(low, np.nan_to_num(u), np.nan_to_num(v), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    projected[~valid] = 0
    # The TMC ortho is already on the matching polar grid at 5 m/px.
    tc = int(round((x0-tgt[0])/5))
    tr = int(round((tgt[3]-y1)/5))
    if not (0 <= tc and 0 <= tr and tc+nx <= tmc.RasterXSize and tr+ny <= tmc.RasterYSize):
        raise RuntimeError("Projected ROI outside TMC ortho")
    tmc_data = tmc.GetRasterBand(1).ReadAsArray(tc,tr,nx,ny)
    def normalize(a, mask=None):
        values = a[mask] if mask is not None else a[a>0]
        lo, hi = np.percentile(values,[1,99])
        return np.clip((a.astype(np.float32)-lo)*255/max(hi-lo,1),0,255).astype(np.uint8)
    ohrc_u8 = normalize(projected,valid)
    tmc_u8 = normalize(tmc_data)
    cv2.imwrite(str(OUT/"ohrc_projected_5m.png"),ohrc_u8)
    cv2.imwrite(str(OUT/"tmc_ortho_5m.png"),tmc_u8)
    cv2.imwrite(str(OUT/"ohrc_valid_mask.png"),valid.astype(np.uint8)*255)
    meta = {"audit_id":(f"REALPAIR005_FULLSTRIP_TILE_{TILE_START:06d}_{TILE_END:06d}_V1" if TILE else
                        {"start":"REALPAIR005_ALIGNED_START_CANDIDATE_V1",
                         "first":"REALPAIR005_ALIGNED_FIRST_CANDIDATE_V1",
                         "middle":"REALPAIR005_ALIGNED_MIDDLE_CANDIDATE_V1",
                         "final":"REALPAIR005_ALIGNED_FINAL_CANDIDATE_V1"}[ROI_KIND]), "ohrc_product_id":OHRC_ID,
            "tmc_product_id":TMC_ID,"dtm_product_id":"ch2_tmc_ndn_20231101T0125121377_d_dtm_d18",
            "output_grid":"TMC polar stereographic 5 m/px", "bbox_m":[x0,y0,x1,y1],
            "shape_px":[nx,ny],"supported_camera_grid_points":len(map_pts),
            "valid_output_fraction":float(valid.mean()),
            "source_roi_native_ohrc_sample_line":[s0+1,l0+1,s1,l1],
            "camera_assumptions":"IK focal length/pixel pitch, SPICE frame/SPK/CK, XML timing; ASP-aligned TMC DTM sampled with local horizontal affine and vertical plane",
            "pointing_prior_true_xy_m":POINTING_PRIOR_TRUE_XY_M.tolist(),
            "pointing_prior_source":"pointing_residual_accounting.json; image-derived training regions, not independently accepted camera correction",
            "navigation_source":"tmc_navigation_affine.json",
            "decision":"ABSTAIN_GEOMETRY_NOT_INDEPENDENTLY_VERIFIED"}
    (OUT/"projection.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))


if __name__ == "__main__":
    main()
