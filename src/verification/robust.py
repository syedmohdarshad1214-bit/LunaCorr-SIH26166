"""Simplest-supported local model with a held-out correspondence check."""

import cv2
import numpy as np

from src.matching.baseline import project_points


MODELS=('translation','similarity','affine','homography')
MINIMUM={'translation':1,'similarity':2,'affine':3,'homography':4}


def residuals(a,b,matrix):
    return np.linalg.norm(project_points(a,matrix)-b,axis=1)


def fit_model(a,b,model,threshold,seed,max_trials):
    if len(a)<MINIMUM[model]:
        return None
    if model in ('affine','homography') and (np.linalg.matrix_rank(a-a.mean(axis=0))<2 or np.linalg.matrix_rank(b-b.mean(axis=0))<2):
        return None
    cv2.setRNGSeed(seed)
    if model=='translation':
        rng=np.random.default_rng(seed)
        deltas=b-a
        best=None
        best_count=0
        for i in rng.choice(len(a),size=min(max_trials,len(a)),replace=False):
            inside=np.linalg.norm(deltas-deltas[i],axis=1)<=threshold
            if inside.sum()>best_count:
                best_count=int(inside.sum())
                best=inside
        if best is None:
            return None
        matrix=np.eye(3)
        matrix[:2,2]=np.median(deltas[best],axis=0)
    elif model=='similarity':
        if np.max(np.linalg.norm(a-a[0],axis=1))<1e-6:
            return None
        value,_=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=threshold,maxIters=max_trials,confidence=.99,refineIters=10)
        if value is None:
            return None
        matrix=np.vstack((value,[0,0,1]))
    elif model=='affine':
        value,_=cv2.estimateAffine2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=threshold,maxIters=max_trials,confidence=.99,refineIters=10)
        if value is None:
            return None
        matrix=np.vstack((value,[0,0,1]))
    else:
        matrix,_=cv2.findHomography(a,b,cv2.RANSAC,threshold,maxIters=max_trials,confidence=.99)
    if matrix is None or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-12:
        return None
    return matrix


def verify(a,b,config):
    required={'models','residual_threshold_px','min_inliers','min_inlier_ratio','holdout_fraction','min_holdout_inliers','min_holdout_ratio','max_holdout_rmse_px','seed','max_trials'}
    if set(config)!=required:
        raise ValueError(f'Robust config needs exactly {sorted(required)}')
    models=config['models']
    if not models or any(m not in MODELS for m in models) or models!=sorted(set(models),key=MODELS.index):
        raise ValueError('Models must be a unique simplest-first subset')
    for key in ('residual_threshold_px','max_holdout_rmse_px'):
        if not np.isfinite(config[key]) or config[key]<=0:
            raise ValueError(f'{key} must be positive')
    for key in ('min_inlier_ratio','min_holdout_ratio'):
        if not 0<config[key]<=1:
            raise ValueError(f'Invalid {key}')
    if not 0<config['holdout_fraction']<.5:
        raise ValueError('Holdout fraction must be between 0 and .5')
    if config['min_inliers']<4 or config['min_holdout_inliers']<2 or not 1<=config['max_trials']<=100000:
        raise ValueError('Invalid minimum support/trial budget')
    a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Correspondences must be matching finite Nx2 arrays')
    n=len(a)
    empty={'model':None,'matrix':None,'inliers':np.zeros(n,dtype=bool),'residuals':np.full(n,np.nan),
           'fit_population':np.zeros(n,dtype=bool),'attempts':[],'reason':'ABSTAIN_INSUFFICIENT_FEATURES'}
    holdout_count=max(config['min_holdout_inliers'],round(n*config['holdout_fraction']))
    if n-holdout_count<config['min_inliers']:
        return empty
    order=np.random.default_rng(config['seed']).permutation(n)
    fit=np.ones(n,dtype=bool)
    fit[order[:holdout_count]]=False
    attempts=[]
    diagnostic=None
    for model in models:
        matrix=fit_model(a[fit],b[fit],model,config['residual_threshold_px'],config['seed'],config['max_trials'])
        if matrix is None:
            attempts.append({'model':model,'accepted':False,'reason':'DEGENERATE_OR_UNSUPPORTED_MODEL'})
            continue
        errors=residuals(a,b,matrix)
        inside=np.isfinite(errors)&(errors<=config['residual_threshold_px'])
        train_count=int((inside&fit).sum())
        held_count=int((inside&~fit).sum())
        held_errors=errors[inside&~fit]
        held_rmse=float(np.sqrt(np.mean(held_errors**2))) if len(held_errors) else None
        accepted=(train_count>=config['min_inliers'] and train_count/int(fit.sum())>=config['min_inlier_ratio']
                  and held_count>=config['min_holdout_inliers'] and held_count/holdout_count>=config['min_holdout_ratio']
                  and held_rmse is not None and held_rmse<=config['max_holdout_rmse_px'])
        attempts.append({'model':model,'accepted':accepted,'fit_inliers':train_count,'fit_candidates':int(fit.sum()),
                         'heldout_inliers':held_count,'heldout_candidates':holdout_count,'heldout_inlier_rmse_target_working_px':held_rmse})
        if diagnostic is None or held_count>diagnostic['held_count']:
            diagnostic={'model':model,'matrix':matrix,'inliers':inside,'residuals':errors,
                        'fit_population':fit,'held_count':held_count}
        if accepted:
            return {'model':model,'matrix':matrix,'inliers':inside,'residuals':errors,'fit_population':fit,
                    'attempts':attempts,'reason':None}
    if diagnostic is not None:
        diagnostic.pop('held_count')
        return dict(diagnostic,attempts=attempts,reason='ABSTAIN_GEOMETRY')
    return dict(empty,fit_population=fit,attempts=attempts,reason='ABSTAIN_GEOMETRY')
