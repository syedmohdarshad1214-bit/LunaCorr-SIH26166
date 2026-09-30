"""Run a prepared overlap-ROI baseline, or check actual acquisition readiness.

This is not yet the full 13-stage live demo. Real inputs require saved geometry,
pixel mapping, browse verification and product-file provenance. No default data.
"""

import argparse
import json
from pathlib import Path
import resource
import sys
import zipfile

import numpy as np

from src.ingest.manifest import local_path,sha256_file,validate_inventory
from src.registration.baseline import run_baseline
from src.evaluation.experiment import save_experiment
from src.matching.baseline import project_points
from src.evaluation.metrics import summarize_errors


ROOT=Path(__file__).resolve().parent


def preflight():
    products=json.loads((ROOT/'data/manifests/products.json').read_text())
    errors=validate_inventory(products)
    counts={key:sum(p.get(key) is not None for p in products) for key in ('xml_file','browse_file','science_file')}
    ready=not errors and all(v>=2 for v in counts.values())
    return {'status':'INPUTS_PRESENT_REVIEW_REQUIRED' if ready else 'BLOCKED_DATA_ACQUISITION',
            'catalogue_products':len(products),'acquired_file_counts':counts,'manifest_errors':errors,
            'real_registration_completed':False,
            'next_step':'Acquire original labels, verify polygon overlap and browse structures, then acquire scoped science data.'}


def execute(config_path):
    config=json.loads(Path(config_path).read_text())
    manifest_path=local_path(ROOT,config['input_manifest'])
    manifest=json.loads(manifest_path.read_text())
    kind=manifest['evidence_type']
    if kind not in ('REAL','SYNTHETIC'):
        raise ValueError('Explicit REAL or SYNTHETIC provenance required')
    files={}
    for name,item in manifest['inputs'].items():
        path=local_path(ROOT,item['path'])
        if sha256_file(path)!=item['sha256']:
            raise ValueError(f'Input checksum mismatch: {name}')
        files[name]=path
    for name in ('roi_bundle','geometry_report','pixel_geometry'):
        if name not in files:
            raise ValueError(f'Missing required input: {name}')
    geometry=json.loads(files['geometry_report'].read_text())
    pixel_geometry=json.loads(files['pixel_geometry'].read_text())
    if kind=='REAL':
        records=manifest['product_records']
        errors=validate_inventory(records)
        if errors:
            raise ValueError('; '.join(errors))
        if len(records)!=2 or {p['product_id'] for p in records}!={config['source_product_id'],config['target_product_id']}:
            raise ValueError('Run product IDs do not match manifest snapshots')
        if any(any(p[key] is None for key in ('xml_file','browse_file','science_file')) for p in records):
            raise ValueError('Real run needs acquired XML, browse, and science files')
        label_hashes={p['checksum'][p['xml_file']] for p in records}
        if {item['sha256'] for item in geometry.get('inputs',[])}!=label_hashes:
            raise ValueError('Geometry report does not reference these exact source labels')
        review=json.loads(files['browse_review'].read_text())
        if review.get('classification')!='BROWSE VERIFIED' or set(review.get('product_ids',[]))!={p['product_id'] for p in records}:
            raise ValueError('A BROWSE VERIFIED review for this exact pair is required')
        for product in records:
            path=product['browse_file']
            if review.get('browse_checksums',{}).get(path)!=product['checksum'][path]:
                raise ValueError('Browse review file hashes do not match the acquired files')
    elif not manifest.get('synthetic_generator'):
        raise ValueError('Synthetic input must record its generator, seed and known transform')
    if geometry.get('status')=='REJECTED (geometry)':
        geometry_status='REJECTED (geometry)'
    elif geometry.get('status')=='ELIGIBLE_FOR_BROWSE' and pixel_geometry.get('status')=='VERIFIED_PIXEL_GEOMETRY':
        # A reviewed preparation artifact, never derived automatically from catalogue proximity.
        if pixel_geometry.get('geometry_report_sha256')!=sha256_file(files['geometry_report']):
            raise ValueError('Pixel geometry is not linked to this exact geometry report')
        if pixel_geometry.get('roi_bundle_sha256')!=sha256_file(files['roi_bundle']):
            raise ValueError('Pixel geometry is not linked to this exact ROI bundle')
        for key in ('source_working_to_native','target_working_to_native','source_to_target_prior',
                    'search_radius_target_working_px','source_product_id','target_product_id','target_working_grid'):
            if pixel_geometry.get(key)!=config[key]:
                raise ValueError(f'Run {key} differs from reviewed pixel geometry')
        geometry_status='VERIFIED_PIXEL_GEOMETRY'
    else:
        geometry_status='UNRESOLVED'
    # The pack contains prepared 2D maps only, never a hyperspectral cube.
    if geometry_status!='VERIFIED_PIXEL_GEOMETRY':
        # Stop before decoding image arrays when the geometry gate fails.
        rows,transform,metrics,images=run_baseline(None,None,None,None,config,geometry_status)
    else:
        rows,transform,metrics,images=run_prepared_bundle(files['roi_bundle'],config,geometry_status)
    metrics['peak_process_memory_bytes']=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
    metrics['memory_definition']='Process peak RSS including interpreter/dependencies and input checks, measured before report rendering.'
    if kind=='SYNTHETIC' and transform['matrix'] is not None:
        points=np.array([[r['source_x_working_px'],r['source_y_working_px']] for r in rows if r['verification_state']=='ROBUST_MODEL_INLIER']).reshape(-1,2)
        truth=manifest['synthetic_generator'].get('known_source_to_target')
        if truth is not None:
            metrics['synthetic_known_transform_error']=summarize_errors(np.linalg.norm(project_points(points,transform['matrix'])-project_points(points,truth),axis=1),config['target_working_grid'],'model versus generator ground truth at inlier locations')
    manifest['input_manifest_sha256']=sha256_file(manifest_path)
    manifest['code_checksums']={str(p.relative_to(ROOT)):sha256_file(p) for p in sorted((ROOT/'src').rglob('*.py'))}
    manifest['code_checksums']['run_demo.py']=sha256_file(Path(__file__))
    # Preserve ROI inputs and metadata. Whole source science files stay hash-referenced.
    copies={name+path.suffix:path for name,path in files.items()}
    copies['input_manifest.json']=manifest_path
    destination=ROOT/'experiments'/config['experiment_id']
    if destination.parent!=ROOT/'experiments':
        raise ValueError('Invalid experiment path')
    return save_experiment(destination,manifest,config,rows,transform,metrics,images,copies)


def run_prepared_bundle(path,config,geometry_status):
    with zipfile.ZipFile(path) as archive:
        members=archive.infolist()
        if len(members)!=4 or {m.filename for m in members}!={'source.npy','target.npy','source_mask.npy','target_mask.npy'}:
            raise ValueError('ROI pack must contain exactly the four documented arrays')
        if sum(m.file_size for m in members)>128*1024*1024:
            raise ValueError('Prepared ROI pack exceeds 128 MiB uncompressed budget')
    with np.load(path,allow_pickle=False) as bundle:
        source,target=bundle['source'],bundle['target']
        mask_a,mask_b=bundle['source_mask'],bundle['target_mask']
        if source.ndim!=2 or target.ndim!=2 or mask_a.shape!=source.shape or mask_b.shape!=target.shape:
            raise ValueError('Prepared arrays must be 2D maps with matching masks')
        if mask_a.dtype!=np.bool_ or mask_b.dtype!=np.bool_:
            raise ValueError('ROI validity masks must be boolean arrays')
        return run_baseline(source,target,mask_a,mask_b,config,geometry_status)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--preflight',action='store_true')
    group.add_argument('--config',type=Path)
    args=parser.parse_args()
    if args.preflight:
        state=preflight()
        print(json.dumps(state,indent=2))
        return 2 if state['status']=='BLOCKED_DATA_ACQUISITION' else 0
    try:
        output=execute(args.config)
        print(json.dumps({'experiment':str(output),'report':str(output/'report.html')}))
        return 0
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as exc:
        print(json.dumps({'status':'INPUT_OR_EXECUTION_ERROR','reason':str(exc)}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
