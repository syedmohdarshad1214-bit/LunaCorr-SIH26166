"""Exact-run residual and distribution metrics; no inferred absolute accuracy."""

import cv2
import numpy as np


def summarize_errors(values,frame,population):
    values=np.asarray(values,dtype=float)
    values=values[np.isfinite(values)]
    return {'frame':frame,'unit':'pixel','population':population,'count':len(values),
      'mean':float(values.mean()) if len(values) else None,
      'median':float(np.median(values)) if len(values) else None,
      'rmse':float(np.sqrt(np.mean(values**2))) if len(values) else None,
      'p90':float(np.percentile(values,90,method='linear')) if len(values) else None,
      'definition':'Euclidean 2D point residual; P90 uses linear quantile interpolation.'}


def spatial_coverage(points,mask,grid_cells=4):
    mask=np.asarray(mask,dtype=bool)
    if mask.ndim!=2 or type(grid_cells) is not int or not 1<=grid_cells<=64:
        raise ValueError('Expected a 2D support mask and grid size 1–64')
    h,w=mask.shape
    eligible=np.zeros((grid_cells,grid_cells),dtype=bool)
    counts=np.zeros((grid_cells,grid_cells),dtype=int)
    for gy in range(grid_cells):
        for gx in range(grid_cells):
            eligible[gy,gx]=mask[gy*h//grid_cells:(gy+1)*h//grid_cells,gx*w//grid_cells:(gx+1)*w//grid_cells].any()
    kept=[]
    for x,y in np.asarray(points).reshape(-1,2):
        if not np.isfinite([x,y]).all():
            continue
        ix,iy=int(round(x)),int(round(y))
        if 0<=ix<w and 0<=iy<h and mask[iy,ix]:
            # Same integer-boundary partition used to determine eligible cells.
            gx=min(grid_cells-1,((ix+1)*grid_cells-1)//w)
            gy=min(grid_cells-1,((iy+1)*grid_cells-1)//h)
            counts[gy,gx]+=1
            kept.append([x,y])
    hull_mask=np.zeros((h,w),dtype=np.uint8)
    if len(kept)>=3:
        hull=cv2.convexHull(np.array(kept,dtype=np.float32))
        if cv2.contourArea(hull)>0:
            cv2.fillConvexPoly(hull_mask,np.rint(hull).astype(np.int32),1)
    denominator=int(eligible.sum())
    support=int(mask.sum())
    return {'occupied_cells':int((counts>0).sum()),'eligible_cells':denominator,
      'grid_coverage':float((counts>0).sum()/denominator) if denominator else None,
      'convex_hull_coverage':float(((hull_mask>0)&mask).sum()/support) if support else None,
      'clustering_max_cell_fraction':float(counts.max()/len(kept)) if kept else None,
      'grid_shape':[grid_cells,grid_cells],'grid_counts':counts.tolist(),'support_pixels':support,
      'definition':'Cells eligible with >=1 valid pixel; hull rasterized at pixel centers and clipped to supplied overlap/validity mask.'}
