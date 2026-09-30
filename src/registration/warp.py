import cv2
import numpy as np


def warp_to_target(source,source_mask,matrix,target_mask):
    """Computed diagnostic warp; acceptance is decided separately."""
    h,w=target_mask.shape
    warped=cv2.warpPerspective(source,np.asarray(matrix,dtype=float),(w,h),flags=cv2.INTER_LINEAR)
    support=cv2.warpPerspective(source_mask.astype(np.uint8),np.asarray(matrix,dtype=float),(w,h),flags=cv2.INTER_NEAREST)>0
    support &= target_mask.astype(bool)
    warped[~support]=0
    return warped,support
