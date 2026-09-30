"""Reproducible SYNTHETIC inputs for offline testing, never real lunar evidence."""
import json
from pathlib import Path
import cv2
import numpy as np
from pyproj import CRS, Transformer
from src.geometry.footprints import parse_label, intersect_footprints
from src.ingest.manifest import sha256_file

ROOT=Path(__file__).resolve().parents[2]
CASES={'success':'Distributed craters', 'shadow':'Dark support', 'flat':'Insufficient structure', 'no_overlap':'Disjoint footprints'}


def write(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def defaults():
    return dict(source_product_id='SYNTHETIC_SOURCE',target_product_id='SYNTHETIC_TARGET',
        source_working_grid='SYNTHETIC source native 640x640 grid',target_working_grid='SYNTHETIC target native 640x640 grid',
        source_working_to_native=np.eye(3).tolist(),target_working_to_native=np.eye(3).tolist(),
        source_to_target_prior=[[1,0,8],[0,1,-5],[0,0,1]],target_working_resolution_m=5,
        normalization_percentiles=[2,98],search_radius_target_working_px=24,
        reverse_search_radius_source_working_px=24,ratio_filter=.78,matcher='SIFT',max_features=2500,
        robust=dict(models=['translation','similarity','affine'],residual_threshold_px=2,
                    min_inliers=12,min_inlier_ratio=.55,holdout_fraction=.25,min_holdout_inliers=4,
                    min_holdout_ratio=.55,max_holdout_rmse_px=1.2,seed=7,max_trials=1000),
        coverage_grid_cells=4,min_grid_coverage=.5,min_hull_coverage=.35,
        require_cycle=True,cycle_enabled=True,cycle_threshold_source_working_px=1.5,
        shadow_mask=True,dark_threshold=12,max_dark_fraction=.65,representation='intensity')


def scene(case):
    rng=np.random.default_rng(19)
    n=640
    z=cv2.GaussianBlur(rng.normal(115,22,(n,n)).astype(np.float32),(5,5),0)
    yy,xx=np.mgrid[:n,:n]
    for _ in range(115):
        x,y=rng.integers(20,n-20,2); radius=rng.integers(5,30)
        distance=np.hypot(xx-x,yy-y)
        rim=np.exp(-((distance-radius)/(radius*.13+1))**2)
        bowl=np.exp(-(distance/(radius*.7))**4)
        z+=rim*(24+32*(xx-x)/(radius+1))-bowl*20
    a=np.clip(z,0,255).astype(np.uint8)
    truth=np.array([[1,0,9],[0,1,-6],[0,0,1]],float)
    b=cv2.warpPerspective(a,truth,(n,n))
    b=np.clip(b.astype(float)*.92+10,0,255).astype(np.uint8)
    mask=np.zeros((n,n),np.uint8); mask[20:-20,20:-20]=1
    mask_b=cv2.warpPerspective(mask,truth,(n,n)).astype(bool)
    if case=='flat': a[:]=100;b[:]=100
    if case=='shadow': a[:560]=0;b[:550]=0
    return a,b,mask.astype(bool),mask_b,truth


def create_pack(destination,case='success',matcher='SIFT',structural=False):
    if case not in CASES or matcher not in ('SIFT','AKAZE'):
        raise ValueError('Unknown demonstration case or matcher')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    a,b,ma,mb,truth=scene(case)
    np.savez_compressed(destination/'roi.npz',source=a,target=b,source_mask=ma,target_mask=mb)
    cv2.imwrite(str(destination/'source.png'),a);cv2.imwrite(str(destination/'target.png'),b)
    ctx=dict(target='Moon',radius_m=1737400,datum='SYNTHETIC lunar sphere',frame='SYNTHETIC fixed frame',
        longitude_direction='east',longitude_domain='-180_180',latitude_type='planetocentric',
        edge_model='shortest_geodesic',metadata_source='LunaCorr synthetic generator, explicit simulation assumptions')
    write(destination/'context.json',ctx)
    lunar=CRS.from_proj4('+proj=longlat +R=1737400 +type=crs')
    local=CRS.from_proj4('+proj=laea +lat_0=-69 +lon_0=20 +R=1737400 +units=m +type=crs')
    to_geo=Transformer.from_crs(local,lunar,always_xy=True)
    labels=[]
    for name,dx,dy in [('SOURCE',0,0),('TARGET',-9,6)]:
        if case=='no_overlap' and name=='TARGET': dx+=1600
        corners=[(-.5,-.5),(639.5,-.5),(639.5,639.5),(-.5,639.5)]
        vertices=[to_geo.transform((x+dx)*5,-(y+dy)*5) for x,y in corners]
        xml=''.join(f'<geom:Pixel_Intercept><geom:pixel_longitude unit="deg">{lon:.12f}</geom:pixel_longitude><geom:pixel_latitude unit="deg">{lat:.12f}</geom:pixel_latitude></geom:Pixel_Intercept>' for lon,lat in vertices)
        label=destination/(name.lower()+'.xml')
        label.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1" xmlns:geom="http://pds.nasa.gov/pds4/geom/v1">
<!-- SYNTHETIC fixture. Not an ISRO label or real lunar observation. -->
<Identification_Area><logical_identifier>urn:synthetic:{name.lower()}</logical_identifier></Identification_Area>
<Observation_Area><Target_Identification><name>Moon</name></Target_Identification></Observation_Area>
<geom:Footprint_Vertices>{xml}</geom:Footprint_Vertices></Product_Observational>''')
        labels.append(parse_label(label,ctx))
    geometry=intersect_footprints(*labels)
    geometry['evidence_type']='SYNTHETIC'
    write(destination/'geometry.json',geometry)
    cfg=defaults();cfg.update(matcher=matcher,representation='gradient' if structural else 'intensity',demo_case=case)
    pixel={k:cfg[k] for k in ('source_working_to_native','target_working_to_native','source_to_target_prior',
        'search_radius_target_working_px','source_product_id','target_product_id','target_working_grid')}
    pixel.update(status='VERIFIED_PIXEL_GEOMETRY',basis='SYNTHETIC simulation camera; approximate prior differs from known truth',
        roi_bundle_sha256=sha256_file(destination/'roi.npz'),geometry_report_sha256=sha256_file(destination/'geometry.json'))
    write(destination/'pixel_geometry.json',pixel)
    inputs={name:{'path':str((destination/file).relative_to(ROOT)),'sha256':sha256_file(destination/file)} for name,file in
        [('roi_bundle','roi.npz'),('geometry_report','geometry.json'),('pixel_geometry','pixel_geometry.json'),
         ('source_label','source.xml'),('target_label','target.xml'),('coordinate_context','context.json'),('source_browse','source.png'),('target_browse','target.png')]}
    manifest=dict(evidence_type='SYNTHETIC',inputs=inputs,
        synthetic_generator={'name':'src/ingest/demo_pack.py','seed':19,'known_source_to_target':truth.tolist(),
            'note':'Same-scale generated crater texture; does not establish cross-sensor capability or resolve the 320x gap.'})
    write(destination/'manifest.json',manifest)
    cfg['input_manifest']=str((destination/'manifest.json').relative_to(ROOT))
    return cfg
