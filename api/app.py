"""Local-only, offline-capable scientific workbench. No network data acquisition."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import csv
import io
import json
from pathlib import Path
import re
import threading
import time
import uuid
import zipfile

from defusedxml import ElementTree as ET
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from run_demo import execute, preflight, ROOT
from src.ingest.demo_pack import create_pack, CASES, write
from src.ingest.manifest import local_path, sha256_file
from src.geometry.footprints import parse_label, intersect_footprints
from src.geometry.catalogue_point import products_at

app=FastAPI(title='LunaCorr',version='0.1.0')
executor=ThreadPoolExecutor(max_workers=1)
jobs={};guard=threading.Lock()


@app.get('/api/catalogue-overlap-at')
def catalogue_overlap_at(lon:float, lat:float):
    if not 0 <= lon <= 360 or not -90 <= lat <= 90:
        raise HTTPException(422,'Use east longitude 0–360 and latitude −90–90')
    products=products_at(ROOT,lon,lat)
    sensors=[sensor for sensor,ids in products.items() if ids]
    return {'longitude_east':lon,'latitude':lat,'product_ids_by_sensor':products,
            'cross_sensor_overlap':len(sensors)>=2,
            'evidence':'Original saved PRADAN catalogue shapefile polygons; no image registration claim'}


@app.middleware('http')
async def local_write_only(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin not in (f'http://{request.headers.get("host")}', f'https://{request.headers.get("host")}'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Cross-origin writes are disabled'},status_code=403)
    return await call_next(request)


@app.get('/api/status')
def status():
    result=preflight()
    runner_registered=any(x['evidence_type']=='REAL' and x['status']=='REGISTERED' for x in experiments())
    try:
        science=science_proof()['decision']
        result['real_local_registration']={'status':science['registration_decision'],
            'scope':science['registration_scope'],'full_strip':science['full_strip_decision'],
            'absolute_ground_accuracy_5m':science['absolute_ground_accuracy_5m_decision']}
    except HTTPException:
        result['real_local_registration']={'status':'UNAVAILABLE'}
    result['real_registration_completed']=runner_registered or result['real_local_registration']['status']=='REGISTERED'
    result['demo_cases']=CASES
    result['active_jobs']=[{'id':k,**v} for k,v in jobs.items() if v['state'] in ('QUEUED','RUNNING')]
    return result


def read_json(path):
    return json.loads(path.read_text())


PROOF_DIR=ROOT/'data/derived/REALPAIR001_verified_v1'
SCIENCE_DIR=ROOT/'data/derived/REALPAIR005_science_v1'
REJECTED_DIR=ROOT/'data/derived/REALPAIR001_adjusted_registration_v5'
REJECTED_PREVIEW_DIR=ROOT/'data/derived/REALPAIR001_camera_audit_v2'


def checked_overlap_proof():
    """Read the frozen review only after checking its artifacts and original inputs."""
    try:
        manifest=read_json(PROOF_DIR/'manifest.json')
        for base,entries in ((PROOF_DIR,manifest['artifact_checksums']),(ROOT,manifest['inputs'])):
            for name,digest in entries.items():
                path=local_path(base,name)
                if not path.is_file() or sha256_file(path)!=digest:
                    raise ValueError(f'Evidence file missing or changed: {name}')
        return manifest
    except (OSError,ValueError,KeyError) as exc:
        raise HTTPException(409,f'Overlap evidence integrity check failed: {exc}')


@app.get('/api/overlap-proof')
def overlap_proof():
    manifest=checked_overlap_proof()
    records=read_json(ROOT/'data/manifests/products.json')
    return dict(id='REALPAIR001',integrity='VERIFIED',manifest=manifest,
        products=[r for pid in manifest['product_ids'] for r in records if r['product_id']==pid],
        **{key:read_json(PROOF_DIR/(name+'.json')) for key,name in
           [('geometry','geometry'),('review','browse_review'),('segments','segment_checks'),
            ('context','context'),('sensitivity','geometry_sensitivity'),('roi','browse_roi_provenance')]})


@app.get('/api/overlap-proof/download')
def overlap_download():
    manifest=checked_overlap_proof();blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PROOF_DIR.iterdir()):
            if path.is_file():archive.write(path,'REALPAIR001/evidence/'+path.name)
        for name in manifest['inputs']:
            archive.write(local_path(ROOT,name),'REALPAIR001/'+name)
    blob.seek(0)
    return StreamingResponse(blob,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="LunaCorr_REALPAIR001_evidence.zip"'})


@app.get('/api/overlap-proof/input/{filename}')
def overlap_input(filename:str):
    manifest=checked_overlap_proof()
    paths=[local_path(ROOT,name) for name in manifest['inputs'] if Path(name).name==filename]
    if len(paths)!=1:raise HTTPException(404,'Not an input of this evidence pack')
    return FileResponse(paths[0],filename=filename)


@app.get('/api/science-proof')
def science_proof():
    """Expose scoped and full-strip REALPAIR005 decisions with intact audits."""
    try:
        for audit_dir, checksum_name in ((SCIENCE_DIR,'aligned_middle_sha256_v2.txt'),
                                         (SCIENCE_DIR/'full_strip_tiles','audit_sha256.txt')):
            for line in (audit_dir/checksum_name).read_text().splitlines():
                digest,name=line.split('  ',1)
                path=local_path(audit_dir,name)
                if not path.is_file() or sha256_file(path)!=digest:
                    raise ValueError(f'Science evidence missing or changed: {name}')
        decision=read_json(SCIENCE_DIR/'aligned_middle_decision.json')
        return {'decision':decision,
                'full_strip_summary':read_json(SCIENCE_DIR/'full_strip_tiles/summary.json'),
                'full_strip_decision':read_json(SCIENCE_DIR/'full_strip_tiles/decision.json'),
                'geometry':read_json(SCIENCE_DIR/'xml_footprint_intersection.json'),
                'sift':read_json(SCIENCE_DIR/'science_roi_aligned_middle_test/SIFT/metrics.json'),
                'akaze':read_json(SCIENCE_DIR/'science_roi_aligned_middle_test/AKAZE/metrics.json'),
                'projection':read_json(SCIENCE_DIR/'science_roi_aligned_middle/projection.json'),
                'integrity':'VERIFIED'}
    except (OSError,ValueError,KeyError) as exc:
        raise HTTPException(409,f'Science evidence integrity check failed: {exc}')


@app.get('/api/products')
def products():
    return read_json(ROOT/'data/manifests/products.json')


@app.get('/api/experiments')
def experiments():
    output=[]
    for folder in sorted((ROOT/'experiments').glob('EXP*'),reverse=True):
        if not (folder/'manifest.json').is_file():continue
        manifest=read_json(folder/'manifest.json');metrics=read_json(folder/'metrics.json');config=read_json(folder/'config.json')
        output.append(dict(id=folder.name,evidence_type=manifest['evidence_type'],created_utc=manifest['created_utc'],
            status=metrics['status'],reason=metrics['reason'],matcher=config['matcher'],representation=config.get('representation','intensity'),
            case=config.get('demo_case','real prepared ROI'),metrics=metrics))
    return output


def folder_for(experiment_id):
    if not re.fullmatch(r'EXP\d{3,}_[A-Z0-9]+_[A-Z0-9]+',experiment_id):raise HTTPException(400,'Invalid experiment ID')
    path=ROOT/'experiments'/experiment_id
    if not path.is_dir():raise HTTPException(404,'Experiment not found')
    return path


@app.get('/api/experiments/{experiment_id}')
def experiment(experiment_id:str):
    folder=folder_for(experiment_id)
    result={name:read_json(folder/(name+'.json')) for name in ('manifest','config','metrics','transform')}
    with (folder/'matches.csv').open() as stream:result['matches']=list(csv.DictReader(stream))
    result['images']=[str(p.relative_to(folder)) for p in sorted(folder.rglob('*.png')) if 'inputs' not in p.parts]
    geo=folder/'inputs/geometry_report.json'
    result['geometry']=read_json(geo) if geo.exists() else None
    return result


@app.get('/api/experiments/{experiment_id}/download')
def download(experiment_id:str):
    folder=folder_for(experiment_id);blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file():archive.write(path,experiment_id+'/'+str(path.relative_to(folder)))
    blob.seek(0)
    return StreamingResponse(blob,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{experiment_id}.zip"'})


class RunRequest(BaseModel):
    case:str='success'
    matcher:str='SIFT'
    structural:bool=False
    prepared_config:str|None=None


def run_job(job_id,request):
    started=time.perf_counter()
    try:
        jobs[job_id].update(state='RUNNING',phase='Preparing provenance and inputs')
        if request.prepared_config:
            config_path=local_path(ROOT,request.prepared_config)
            if config_path not in list((ROOT/'data/derived').glob('*/config.json')):
                raise ValueError('Choose a discovered prepared config under data/derived/<pack>/config.json')
            cfg=read_json(config_path)
        else:
            pack=ROOT/'data/derived'/('demo_'+job_id)
            cfg=create_pack(pack,request.case,request.matcher,request.structural)
        existing=[int(p.name.split('_')[0][3:]) for p in (ROOT/'experiments').glob('EXP*') if re.match(r'EXP\d+_',p.name)]
        cfg['experiment_id']=f'EXP{max(existing,default=0)+1:03d}_SOURCE_TARGET'
        launch=ROOT/'data/derived'/('run_'+job_id);launch.mkdir()
        config_path=launch/'config.json';write(config_path,cfg)
        jobs[job_id]['phase']='Computing geometry gates, matches, robust models and validation'
        output=execute(config_path)
        jobs[job_id].update(state='COMPLETE',phase='Experiment saved',experiment_id=output.name,elapsed_s=time.perf_counter()-started)
    except Exception as exc:
        jobs[job_id].update(state='ERROR',phase='Run stopped',error=str(exc),elapsed_s=time.perf_counter()-started)


@app.post('/api/run',status_code=202)
def run(request:RunRequest):
    if request.case not in CASES or request.matcher not in ('SIFT','AKAZE'):raise HTTPException(400,'Unknown case or matcher')
    with guard:
        if any(j['state'] in ('QUEUED','RUNNING') for j in jobs.values()):raise HTTPException(409,'A run is already active')
        job_id=uuid.uuid4().hex[:12];jobs[job_id]={'state':'QUEUED','phase':'Queued','created_utc':datetime.now(timezone.utc).isoformat()}
        executor.submit(run_job,job_id,request)
    return {'job_id':job_id}


@app.get('/api/jobs/{job_id}')
def job(job_id:str):
    if job_id not in jobs:raise HTTPException(404,'Unknown job')
    return jobs[job_id]


@app.get('/api/prepared')
def prepared():
    output=[]
    for path in (ROOT/'data/derived').glob('*/config.json'):
        if path.parent.name.startswith('run_'):continue
        output.append({'path':str(path.relative_to(ROOT)),'name':path.parent.name})
    return output


def inspect_file(path):
    item={'path':str(path.relative_to(ROOT)),'name':path.name,'bytes':path.stat().st_size,'sha256':sha256_file(path)}
    if path.suffix.lower()=='.xml':
        try:
            if path.stat().st_size>16*1024*1024:raise ValueError('XML exceeds 16 MiB')
            root=ET.parse(path).getroot()
            fields={}
            for node in root.iter():
                tag=node.tag.split('}')[-1]
                if tag in ('logical_identifier','start_date_time','stop_date_time','file_name','data_type','pixel_resolution','imaging_orbit_number'):
                    fields.setdefault(tag,[]).append((node.text or '').strip())
            item['metadata']=fields
            item['axes']=[{c.tag.split('}')[-1]:(c.text or '').strip() for c in n} for n in root.iter() if n.tag.split('}')[-1]=='Axis_Array']
            item['status']='XML_PARSED_NOT_GEOMETRY_VERIFIED'
        except Exception as exc:item.update(status='INVALID_XML',error=str(exc))
    return item


@app.get('/api/imports')
def imports():
    paths=set((ROOT/'data/imports').glob('*/*'))|set((ROOT/'data/labels').glob('*.xml'))
    return [inspect_file(p) for p in sorted(paths) if p.is_file()]


@app.post('/api/import')
async def import_file(request:Request,name:str):
    if Path(name).name!=name or not re.fullmatch(r'[A-Za-z0-9_. -]{1,180}',name) or Path(name).suffix.lower() not in ('.xml','.png','.jpg','.jpeg','.json'):
        raise HTTPException(400,'Use an XML, PNG, JPG or JSON file with a simple filename')
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>32*1024*1024:raise HTTPException(413,'32 MiB per file; put large science files directly in data/science')
    if Path(name).suffix.lower()=='.xml':
        if len(data)>16*1024*1024:raise HTTPException(413,'16 MiB XML limit')
        try:ET.fromstring(bytes(data))
        except Exception as exc:raise HTTPException(400,f'Invalid XML: {exc}')
    folder=ROOT/'data/imports'/uuid.uuid4().hex[:12];folder.mkdir(parents=True)
    path=folder/name;path.write_bytes(data)
    return inspect_file(path)


class GeometryRequest(BaseModel):
    source_label:str
    target_label:str
    source_context:dict
    target_context:dict
    source_profile:str='geom_vertices'
    target_profile:str='geom_vertices'


@app.post('/api/geometry')
def geometry(request:GeometryRequest):
    try:
        a=local_path(ROOT,request.source_label);b=local_path(ROOT,request.target_label)
        if not all(p.is_relative_to(ROOT/'data') and p.suffix.lower()=='.xml' for p in (a,b)):raise ValueError('Choose XML files under data/')
        report=intersect_footprints(parse_label(a,request.source_context,request.source_profile),parse_label(b,request.target_context,request.target_profile))
    except Exception as exc:
        report={'status':'UNRESOLVED_GEOMETRY','reason':str(exc),'registration_verified':False}
    folder=ROOT/'data/derived'/('geometry_'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    write(folder/'request.json',request.model_dump());write(folder/'geometry.json',report)
    return dict(report,report_path=str((folder/'geometry.json').relative_to(ROOT)))


app.mount('/artifacts',StaticFiles(directory=ROOT/'experiments'),name='artifacts')
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
app.mount('/overlap-evidence',StaticFiles(directory=PROOF_DIR),name='overlap-evidence')
app.mount('/science-evidence',StaticFiles(directory=SCIENCE_DIR),name='science-evidence')
app.mount('/rejected-evidence',StaticFiles(directory=REJECTED_DIR),name='rejected-evidence')
app.mount('/rejected-preview',StaticFiles(directory=REJECTED_PREVIEW_DIR),name='rejected-preview')


@app.get('/')
def index():return FileResponse(ROOT/'frontend/index.html')
