"""SIFT/AKAZE descriptors with per-feature bounded search and ratio filtering."""

import cv2
import numpy as np
from scipy.spatial import cKDTree


def project_points(points,matrix):
    points=np.asarray(points,dtype=np.float64).reshape(-1,2)
    matrix=np.asarray(matrix,dtype=np.float64)
    if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-12:
        raise ValueError('Expected a finite, nonsingular 3x3 transform')
    homogeneous=np.column_stack((points,np.ones(len(points))))@matrix.T
    result=np.full((len(points),2),np.nan)
    good=np.abs(homogeneous[:,2])>1e-12
    result[good]=homogeneous[good,:2]/homogeneous[good,2,None]
    return result


def bounded_matches(source,target,source_mask,target_mask,prior,search_radius_px,ratio,matcher='SIFT',max_features=4000):
    if not 0<ratio<1 or not np.isfinite(search_radius_px) or search_radius_px<=0:
        raise ValueError('Explicit ratio (0,1) and positive search radius required')
    if type(max_features) is not int or not 2<=max_features<=20000:
        raise ValueError('Feature budget must be 2–20000')
    if matcher=='SIFT':
        detector=cv2.SIFT_create(nfeatures=max_features)
        norm=cv2.NORM_L2
    elif matcher=='AKAZE':
        detector=cv2.AKAZE_create()
        norm=cv2.NORM_HAMMING
    else:
        raise ValueError('Implemented baselines are SIFT and AKAZE')
    keypoints=[]
    descriptors=[]
    for image,mask in ((source,source_mask),(target,target_mask)):
        if image.dtype!=np.uint8 or image.ndim!=2 or mask.shape!=image.shape:
            raise ValueError('Expected normalized uint8 image and matching mask')
        points,desc=detector.detectAndCompute(image,mask.astype(np.uint8)*255)
        if desc is not None and len(points)>max_features:
            keep=sorted(range(len(points)),key=lambda i:points[i].response,reverse=True)[:max_features]
            points=[points[i] for i in keep]
            desc=desc[keep]
        keypoints.append(points)
        descriptors.append(desc)
    empty=np.empty((0,2),dtype=float)
    counts={'source_features':len(keypoints[0]),'target_features':len(keypoints[1])}
    if descriptors[0] is None or descriptors[1] is None or len(keypoints[1])<2:
        return empty,empty,[],counts
    xy_a=np.array([p.pt for p in keypoints[0]])
    xy_b=np.array([p.pt for p in keypoints[1]])
    predictions=project_points(xy_a,prior)
    tree=cKDTree(xy_b)
    bf=cv2.BFMatcher(norm)
    candidates=[]
    for index,predicted in enumerate(predictions):
        if not np.isfinite(predicted).all():
            continue
        targets=tree.query_ball_point(predicted,search_radius_px)
        if len(targets)<2:
            continue
        pair=bf.knnMatch(descriptors[0][index:index+1],descriptors[1][targets],k=2)[0]
        if len(pair)==2 and pair[0].distance<ratio*pair[1].distance:
            best=pair[0]
            candidates.append({'source_feature':index,'target_feature':targets[best.trainIdx],
              'descriptor_source':matcher,'distance':float(best.distance),
              'ratio':float(best.distance/pair[1].distance),'predicted_target_px':predicted.tolist(),
              'search_radius_target_working_px':float(search_radius_px)})
    # Each target descriptor contributes once; repeated target claims are discarded.
    selected=[]
    used=set()
    for item in sorted(candidates,key=lambda x:(x['ratio'],x['distance'],x['source_feature'])):
        if item['target_feature'] not in used:
            used.add(item['target_feature'])
            selected.append(item)
    return np.array([xy_a[m['source_feature']] for m in selected]).reshape(-1,2),np.array([xy_b[m['target_feature']] for m in selected]).reshape(-1,2),selected,counts
