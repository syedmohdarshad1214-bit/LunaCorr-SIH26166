"""Baseline pipeline on prepared, provenance-bearing overlap grids.

This harness does not invent pixel geometry from footprint corners. A prepared
ROI bundle must retain its native transforms and externally established support.
"""

import time
import cv2
import numpy as np

from src.preprocessing.optical import normalize
from src.matching.baseline import bounded_matches,project_points
from src.verification.robust import verify
from src.evaluation.metrics import summarize_errors,spatial_coverage
from src.registration.warp import warp_to_target
from src.preprocessing.structural import layers
from src.verification.cycle import reverse_cycle


def run_baseline(source,target,source_mask,target_mask,config,geometry_status):
    started=time.perf_counter()
    frame=config['target_working_grid']
    metrics={'status':'ABSTAIN','reason':None,'candidate_count':0,'inlier_count':0,'inlier_ratio':None,
             'cycle_closure_error':None,'cycle_check':'UNAVAILABLE_IN_BASELINE',
             'ground_error_m':None,'ground_error_reference':'UNAVAILABLE',
             'confidence':None,'confidence_calibration':'UNCALIBRATED',
             'target_working_grid':frame,'runtime_s':None,
             'scope':'Prepared overlap-grid baseline; held-out image matches are not independent ground truth.'}
    transform={'model':None,'matrix':None,'direction':'source_working_to_target_working','accepted':False,
               'source_working_to_native':config['source_working_to_native'],
               'target_working_to_native':config['target_working_to_native'],'model_attempts':[]}
    rows=[]
    images={}
    def finish():
        metrics['runtime_s']=time.perf_counter()-started
        metrics['software']={'opencv':cv2.__version__,'numpy':np.__version__}
        return rows,transform,metrics,images
    if geometry_status=='REJECTED (geometry)':
        metrics.update(status='REJECTED (geometry)',reason='REJECT_GEOMETRY')
        return finish()
    if geometry_status!='VERIFIED_PIXEL_GEOMETRY':
        metrics['reason']='ABSTAIN_UNRESOLVED_PIXEL_GEOMETRY'
        return finish()
    if len(frame.strip())==0:
        raise ValueError('Target sensor and working grid must be named')
    a,mask_a,norm_a=normalize(source,source_mask,config['normalization_percentiles'])
    b,mask_b,norm_b=normalize(target,target_mask,config['normalization_percentiles'])
    metrics['normalization']={'source':norm_a,'target':norm_b}
    images.update({'previews/source_normalized.png':a,'previews/target_normalized.png':b})
    if not norm_a['usable'] or not norm_b['usable']:
        metrics['reason']='ABSTAIN_INSUFFICIENT_FEATURES'
        return finish()
    _, structure_a, dark_a, clean_a, _=layers(source,mask_a,config.get('dark_threshold',12))
    _, structure_b, dark_b, clean_b, _=layers(target,mask_b,config.get('dark_threshold',12))
    images.update({'previews/source_structural.png':structure_a,'previews/target_structural.png':structure_b,
                   'previews/source_dark_mask.png':dark_a.astype(np.uint8)*255,'previews/target_dark_mask.png':dark_b.astype(np.uint8)*255})
    metrics['dark_pixel_fraction']={'source':float(dark_a.sum()/max(1,mask_a.sum())), 'target':float(dark_b.sum()/max(1,mask_b.sum()))}
    metrics['mask_method']='Normalized intensity threshold; shadow proxy, not a physical illumination model'
    if config.get('shadow_mask',False):
        if max(metrics['dark_pixel_fraction'].values())>config.get('max_dark_fraction',.65):
            metrics['reason']='ABSTAIN_SHADOW'
            return finish()
        mask_a,mask_b=clean_a,clean_b
    match_a,match_b=(structure_a,structure_b) if config.get('representation')=='gradient' else (a,b)
    metrics['representation']=config.get('representation','intensity')
    xy_a,xy_b,provenance,feature_counts=bounded_matches(match_a,match_b,mask_a,mask_b,
        config['source_to_target_prior'],config['search_radius_target_working_px'],
        config['ratio_filter'],config['matcher'],config['max_features'])
    metrics.update(feature_counts,candidate_count=len(xy_a))
    result=verify(xy_a,xy_b,config['robust'])
    inside=result['inliers']
    fit=result['fit_population']
    metrics['inlier_count']=int(inside.sum())
    metrics['inlier_ratio']=float(inside.mean()) if len(inside) else None
    metrics['inlier_errors']=summarize_errors(result['residuals'][inside],frame,'all robust-model inliers')
    metrics['heldout_inlier_errors']=summarize_errors(result['residuals'][inside&~fit],frame,'held-out inliers, excluded from fitting')
    metrics['all_candidate_errors']=summarize_errors(result['residuals'],frame,'all tentative candidates')
    metrics['spatial_coverage']={
      'source':spatial_coverage(xy_a[inside],mask_a,config['coverage_grid_cells']),
      'target':spatial_coverage(xy_b[inside],mask_b,config['coverage_grid_cells'])}
    native_a=project_points(xy_a,config['source_working_to_native'])
    native_b=project_points(xy_b,config['target_working_to_native'])
    for index,item in enumerate(provenance):
        error=result['residuals'][index]
        state=('ROBUST_MODEL_INLIER' if inside[index] else 'ROBUST_MODEL_OUTLIER') if result['matrix'] is not None else 'TENTATIVE_UNVERIFIED'
        rows.append(dict(match_id=index+1,source_x_working_px=float(xy_a[index,0]),source_y_working_px=float(xy_a[index,1]),
          target_x_working_px=float(xy_b[index,0]),target_y_working_px=float(xy_b[index,1]),
          source_x_native_px=float(native_a[index,0]),source_y_native_px=float(native_a[index,1]),
          target_x_native_px=float(native_b[index,0]),target_y_native_px=float(native_b[index,1]),
          descriptor_source=item['descriptor_source']+':'+metrics['representation'],descriptor_distance=item['distance'],ratio=item['ratio'],
          verification_state=state,population='FIT' if fit[index] else 'HELD_OUT',
          residual_target_working_px=float(error) if np.isfinite(error) else None,
          source_product_id=config['source_product_id'],target_product_id=config['target_product_id']))
    transform.update(model=result['model'],matrix=result['matrix'].tolist() if result['matrix'] is not None else None,model_attempts=result['attempts'])
    if result['matrix'] is not None:
        warped,support=warp_to_target(a,mask_a,result['matrix'],mask_b)
        images['overlays/diagnostic_warp.png']=warped
        images['overlays/warp_valid_support.png']=support.astype(np.uint8)*255
        images['overlays/target_warp_blend.png']=cv2.addWeighted(warped,.5,b,.5,0)
    # Correspondence visualization labels green/red by robust state, not final CP acceptance.
    canvas=np.zeros((max(a.shape[0],b.shape[0]),a.shape[1]+b.shape[1],3),dtype=np.uint8)
    canvas[:a.shape[0],:a.shape[1]]=cv2.cvtColor(a,cv2.COLOR_GRAY2BGR)
    canvas[:b.shape[0],a.shape[1]:]=cv2.cvtColor(b,cv2.COLOR_GRAY2BGR)
    for i,(pa,pb) in enumerate(zip(xy_a,xy_b)):
        color=(40,180,40) if inside[i] else (40,40,230)
        cv2.line(canvas,tuple(np.rint(pa).astype(int)),(int(round(pb[0]))+a.shape[1],int(round(pb[1]))),color,1)
    images['overlays/robust_correspondences.png']=canvas
    if result['reason']:
        metrics['reason']=result['reason']
    elif any((coverage['grid_coverage'] or 0)<config['min_grid_coverage'] or (coverage['convex_hull_coverage'] or 0)<config['min_hull_coverage'] for coverage in metrics['spatial_coverage'].values()):
        metrics['reason']='ABSTAIN_CLUSTERED_MATCHES'
    elif config.get('cycle_enabled',False):
        cycle=reverse_cycle(match_a,match_b,mask_a,mask_b,result['matrix'],xy_a[inside],config)
        metrics['cycle_closure_error']=cycle
        metrics['cycle_check']=cycle['status']
        if cycle['status']!='MEASURED':
            metrics['reason']='ABSTAIN_CYCLE_UNAVAILABLE'
        elif cycle['p90']>config.get('cycle_threshold_source_working_px',2):
            metrics.update(status='REJECTED (consistency)',reason='REJECT_INCONSISTENT_CYCLE')
        else:
            metrics.update(status='REGISTERED',reason='PAIR_GEOMETRY_IMAGE_AND_REVERSE_CYCLE_PASSED')
            transform['accepted']=True
    elif config['require_cycle']:
        metrics['reason']='ABSTAIN_CYCLE_UNAVAILABLE'
    else:
        metrics.update(status='REGISTERED',reason='PAIR_GEOMETRY_AND_IMAGE_CHECKS_PASSED')
        transform['accepted']=True
    if metrics['inlier_errors']['rmse'] is not None and config.get('target_working_resolution_m'):
        metrics['ground_residual_m']=metrics['inlier_errors']['rmse']*config['target_working_resolution_m']
        metrics['ground_residual_definition']='Relative image-model RMSE scaled by target working metres/pixel; not absolute lunar ground accuracy.'
    if transform['accepted']:
        coverage=min(c['grid_coverage'] or 0 for c in metrics['spatial_coverage'].values())
        metrics['confidence']=float(min(metrics['inlier_ratio'],coverage))
        metrics['confidence_calibration']='UNCALIBRATED_SUPPORT_SCORE: minimum of inlier ratio and occupied-grid fraction; not probability or ground accuracy'
    return finish()
