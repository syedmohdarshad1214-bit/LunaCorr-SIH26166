"""Prepare reviewed, same-CRS lunar GeoTIFFs by reading only their overlap.

Usage: .venv/bin/python prepare_pair.py --request data/pair_request.json --name my_pair
Raw camera products need external camera/DEM preparation; this adapter never
infers a pixel map from footprint corners alone.
"""
import argparse
import json
from pathlib import Path
import re

import cv2
import numpy as np
from pyproj import CRS,Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import transform as project_shape

from run_demo import ROOT
from src.geometry.footprints import parse_label,intersect_footprints
from src.ingest.manifest import local_path,sha256_file,validate_inventory
from src.ingest.demo_pack import defaults,write
from src.preprocessing.optical import normalize


def affine_matrix(affine):
    return np.array([[affine.a,affine.b,affine.c],[affine.d,affine.e,affine.f],[0,0,1]],float)


def native_mapping(native,working):
    center=np.array([[1,0,.5],[0,1,.5],[0,0,1.]])
    return np.linalg.inv(center)@np.linalg.inv(affine_matrix(native))@affine_matrix(working)@center


def prepare(request,destination):
    records=request['product_records']
    errors=validate_inventory(records)
    if errors:raise ValueError('; '.join(errors))
    if len(records)!=2:raise ValueError('Exactly two ordered product records required: source, target')
    for r in records:
        if any(r.get(k) is None for k in ('xml_file','browse_file','science_file')):raise ValueError('Each product needs original XML, browse and science paths with checksums')
    if request.get('orthorectified_reviewed') is not True or not request.get('geometry_basis','').strip():
        raise ValueError('Document reviewed orthorectification/camera basis; raw footprints do not give pixel geometry')
    review=read(request['browse_review'])
    if review.get('classification')!='BROWSE VERIFIED' or not review.get('repeated_structures') or not review.get('reviewer'):
        raise ValueError('A named human browse review describing repeated structures is required')
    if set(review.get('product_ids',[]))!={r['product_id'] for r in records}:raise ValueError('Browse review product IDs differ')
    if any(review.get('browse_checksums',{}).get(r['browse_file'])!=r['checksum'][r['browse_file']] for r in records):raise ValueError('Browse review hashes differ')
    labels=[parse_label(local_path(ROOT,r['xml_file']),request['contexts'][i],request['profiles'][i]) for i,r in enumerate(records)]
    for label,record in zip(labels,records):
        if label.product_id.split(':')[-1].lower()!=record['product_id'].lower():raise ValueError('Original label product ID differs from record')
    geometry=intersect_footprints(*labels)
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Prepared folders are never overwritten; choose a new name')
    destination.mkdir(parents=True)
    write(destination/'request.json',request);write(destination/'geometry.json',geometry)
    if geometry['status']!='ELIGIBLE_FOR_BROWSE':
        return {'status':geometry['status'],'geometry_report':str(destination/'geometry.json'),'note':'Stopped before raster reads.'}
    selections=request['bands']
    if len(selections)!=2:raise ValueError('Supply one band list per source and target')
    if not request.get('band_selection_reason','').strip():raise ValueError('Document band selection and physical meaning')
    with rasterio.open(local_path(ROOT,records[0]['science_file'])) as source, rasterio.open(local_path(ROOT,records[1]['science_file'])) as target:
        if not source.crs or source.crs!=target.crs:raise ValueError('Both rasters must have the same documented projected lunar CRS; prepare camera products externally')
        crs=CRS.from_user_input(source.crs)
        if not crs.is_projected or any(ax.unit_name!='metre' for ax in crs.axis_info):raise ValueError('Projected metre units required')
        radius=request['contexts'][0]['radius_m']
        if abs(crs.ellipsoid.semi_major_metre-radius)>1 or abs(crs.ellipsoid.semi_minor_metre-radius)>1:
            raise ValueError('Raster CRS ellipsoid differs from declared lunar sphere')
        transformer=Transformer.from_crs(CRS.from_wkt(geometry['crs_wkt']),crs,always_xy=True,allow_ballpark=False)
        overlap=project_shape(transformer.transform,wkt.loads(geometry['intersection_wkt']))
        # Clip to actual raster envelopes in their shared projected CRS.
        from shapely.geometry import Polygon
        for ds in (source,target):
            overlap=overlap.intersection(Polygon([ds.transform*p for p in [(0,0),(ds.width,0),(ds.width,ds.height),(0,ds.height)]]))
        if overlap.is_empty or overlap.area<=0:raise ValueError('XML overlap has no support inside these raster footprints')
        xmin,ymin,xmax,ymax=overlap.bounds
        res=max(float(request.get('working_resolution_m',0)),*[np.linalg.norm([ds.transform.a,ds.transform.d]) for ds in (source,target)],*[np.linalg.norm([ds.transform.b,ds.transform.e]) for ds in (source,target)])
        res=max(res,(xmax-xmin)/1024,(ymax-ymin)/1024)
        width=max(1,int(np.ceil((xmax-xmin)/res)));height=max(1,int(np.ceil((ymax-ymin)/res)))
        working=from_origin(xmin,ymax,res,res)
        support=geometry_mask([mapping(overlap)],out_shape=(height,width),transform=working,invert=True)
        arrays=[];masks=[];maps=[];meta=[]
        for ds,bands in zip((source,target),selections):
            if not bands or len(bands)>8 or len(set(bands))!=len(bands) or any(type(b) is not int or b<1 or b>ds.count for b in bands):
                raise ValueError('Choose 1–8 distinct valid one-based band indices per image')
            if ds.count>8 and len(bands)>=ds.count:raise ValueError('Do not indiscriminately read an entire hyperspectral cube')
            with WarpedVRT(ds,crs=ds.crs,transform=working,width=width,height=height,resampling=Resampling.average,dtype='float32',nodata=float('nan'),warp_mem_limit=64) as roi:
                cube=roi.read(bands,masked=True)
                valid=(~np.ma.getmaskarray(cube)).all(axis=0)&np.isfinite(cube.filled(np.nan)).all(axis=0)&support
                summary=cube.filled(0).mean(axis=0);summary[~valid]=np.nan
            arrays.append(summary);masks.append(valid);maps.append(native_mapping(ds.transform,working).tolist())
            meta.append({'native_shape':[ds.height,ds.width],'bands_1_based':bands,'native_transform':list(ds.transform),'working_to_native':maps[-1]})
        common=masks[0]&masks[1]
        if common.sum()<100:raise ValueError('Too little shared valid raster support')
        np.savez_compressed(destination/'roi.npz',source=arrays[0],target=arrays[1],source_mask=common,target_mask=common)
        for name,arr in zip(('source','target'),arrays):
            gray,_,_=normalize(arr,common);cv2.imwrite(str(destination/(name+'.png')),gray)
        write(destination/'raster_preparation.json',dict(method='Windowed GDAL warped VRT; band mean of explicitly selected bands',
            band_selection_reason=request['band_selection_reason'],working_crs_wkt=crs.to_wkt(),working_transform=list(working),
            working_resolution_m=res,working_shape=[height,width],native=meta,whole_cube_materialized=False,
            geometry_basis=request['geometry_basis'],support_pixels=int(common.sum())))
    cfg=defaults()
    cfg.update(source_product_id=records[0]['product_id'],target_product_id=records[1]['product_id'],
        source_working_grid=f'{records[0]["sensor"]} common projected {width}x{height} ROI at {res:g} m/px',
        target_working_grid=f'{records[1]["sensor"]} common projected {width}x{height} ROI at {res:g} m/px',
        source_working_to_native=maps[0],target_working_to_native=maps[1],source_to_target_prior=np.eye(3).tolist(),
        target_working_resolution_m=res,search_radius_target_working_px=float(request['search_radius_working_px']),
        reverse_search_radius_source_working_px=float(request['search_radius_working_px']))
    pixel={k:cfg[k] for k in ('source_working_to_native','target_working_to_native','source_to_target_prior','search_radius_target_working_px','source_product_id','target_product_id','target_working_grid')}
    pixel.update(status='VERIFIED_PIXEL_GEOMETRY',basis=request['geometry_basis'],roi_bundle_sha256=sha256_file(destination/'roi.npz'),geometry_report_sha256=sha256_file(destination/'geometry.json'))
    write(destination/'pixel_geometry.json',pixel)
    files={'roi_bundle':destination/'roi.npz','geometry_report':destination/'geometry.json','pixel_geometry':destination/'pixel_geometry.json',
        'browse_review':local_path(ROOT,request['browse_review']),'raster_preparation':destination/'raster_preparation.json',
        'source_label':local_path(ROOT,records[0]['xml_file']),'target_label':local_path(ROOT,records[1]['xml_file']),
        'source_browse':destination/'source.png','target_browse':destination/'target.png'}
    manifest=dict(evidence_type='REAL',product_records=records,inputs={k:{'path':str(p.relative_to(ROOT)),'sha256':sha256_file(p)} for k,p in files.items()})
    write(destination/'manifest.json',manifest)
    cfg['input_manifest']=str((destination/'manifest.json').relative_to(ROOT));cfg['experiment_id']=request['experiment_id']
    write(destination/'config.json',cfg)
    return {'status':'PREPARED_REVIEWED_REAL_PAIR','config':str(destination/'config.json'),'working_resolution_m':res}


def read(path):return json.loads(local_path(ROOT,path).read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',required=True);parser.add_argument('--name',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.name):parser.error('Use a simple new pack name')
    try:print(json.dumps(prepare(read(args.request),ROOT/'data/derived'/args.name),indent=2))
    except Exception as exc:raise SystemExit(f'Preparation stopped: {exc}')
