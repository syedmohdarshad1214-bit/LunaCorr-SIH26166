"""Small, traceable preprocessing baseline; no hidden whole-scene operations."""

import cv2
import numpy as np


def normalize(image, valid, percentiles=(2,98)):
    image=np.asarray(image)
    valid=np.asarray(valid,dtype=bool)&np.isfinite(image)
    if image.ndim!=2 or valid.shape!=image.shape:
        raise ValueError('Image and validity must be matching 2D arrays')
    if len(percentiles)!=2 or not 0<=percentiles[0]<percentiles[1]<=100:
        raise ValueError('Invalid normalization percentiles')
    result=np.zeros(image.shape,dtype=np.uint8)
    values=image[valid]
    if values.size<16:
        return result,valid,{'usable':False,'reason':'INSUFFICIENT_VALID_PIXELS'}
    low,high=np.percentile(values,percentiles)
    if high<=low:
        return result,valid,{'usable':False,'reason':'FLAT_COMMON_SUPPORT'}
    result[valid]=np.clip((values-low)/(high-low)*255,0,255).astype(np.uint8)
    return result,valid,{'usable':True,'percentiles':list(percentiles),'low':float(low),'high':float(high)}


def downsample(image,valid,factor):
    """Create a new context grid; return the pixel-center mapping to its parent."""
    if not np.isfinite(factor) or factor<1:
        raise ValueError('Context scale requires a finite downsampling factor >= 1')
    h,w=image.shape
    oh,ow=max(1,round(h/factor)),max(1,round(w/factor))
    weight=cv2.resize(valid.astype(np.float32),(ow,oh),interpolation=cv2.INTER_AREA)
    total=cv2.resize(np.where(valid,image,0).astype(np.float32),(ow,oh),interpolation=cv2.INTER_AREA)
    out=total/np.maximum(weight,1e-12)
    mask=weight>=.999
    out[~mask]=np.nan
    sx,sy=w/ow,h/oh
    return out,mask,np.array([[sx,0,(sx-1)/2],[0,sy,(sy-1)/2],[0,0,1]],dtype=float)
