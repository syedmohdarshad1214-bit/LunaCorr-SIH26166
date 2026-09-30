"""Exclusive experiment creation with frozen artifacts and offline HTML reports."""

import csv
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil

import cv2
import numpy as np

from src.ingest.manifest import sha256_file


MATCH_FIELDS=['match_id','source_x_working_px','source_y_working_px','target_x_working_px','target_y_working_px',
              'source_x_native_px','source_y_native_px','target_x_native_px','target_y_native_px',
              'descriptor_source','descriptor_distance','ratio','verification_state','population',
              'residual_target_working_px','source_product_id','target_product_id']


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def save_experiment(destination,manifest,config,matches,transform,metrics,images=None,inputs=None):
    """Caller supplies a new explicit ID; final/staging directories are never overwritten."""
    destination=Path(destination)
    if not re.fullmatch(r'EXP\d{3,}_[A-Z0-9]+_[A-Z0-9]+',destination.name):
        raise ValueError('Experiment name must follow EXP001_OHRC_TMC style')
    if manifest.get('evidence_type') not in ('REAL','SYNTHETIC'):
        raise ValueError('Explicit REAL or SYNTHETIC evidence_type required')
    if destination.exists():
        raise FileExistsError(f'Immutable experiment already exists: {destination}')
    staging=destination.with_name('.'+destination.name+'.staging')
    staging.mkdir(parents=True,exist_ok=False)
    (staging/'previews').mkdir()
    (staging/'overlays').mkdir()
    (staging/'inputs').mkdir()
    write_json(staging/'config.json',config)
    write_json(staging/'transform.json',transform)
    write_json(staging/'metrics.json',metrics)
    for name,rows in [('matches.csv',matches),('inliers.csv',[m for m in matches if m['verification_state']=='ROBUST_MODEL_INLIER'])]:
        with (staging/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=MATCH_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    for name,source in (inputs or {}).items():
        if Path(name).name!=name:
            raise ValueError('Input artifact names must be flat basenames')
        shutil.copyfile(source,staging/'inputs'/name)
    image_links=[]
    for name,value in (images or {}).items():
        if not re.fullmatch(r'(previews|overlays)/[a-z0-9_]+\.png',name):
            raise ValueError('Unexpected image artifact path')
        value=np.asarray(value)
        # Bake provenance into the image, including when it is used outside the report.
        if value.ndim==2:
            value=cv2.cvtColor(value.astype(np.uint8),cv2.COLOR_GRAY2BGR)
        canvas=cv2.copyMakeBorder(value,28,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        title=f'{manifest["evidence_type"]} | {destination.name} | {metrics.get("status","UNAVAILABLE")}'
        cv2.putText(canvas,title,(6,19),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA)
        if not cv2.imwrite(str(staging/name),canvas):
            raise OSError(f'Failed to write {name}')
        image_links.append(f'<figure><img src="{name}" alt="{html.escape(name)}"><figcaption>{html.escape(name)}</figcaption></figure>')
    manifest=dict(manifest,experiment_id=destination.name,created_utc=datetime.now(timezone.utc).isoformat())
    report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{destination.name}</title>
<style>body{{max-width:1100px;margin:32px auto;padding:0 20px;font:16px system-ui;color:#17202a}}pre{{white-space:pre-wrap;background:#eef1f3;padding:16px}}img{{max-width:100%}}strong{{color:#843900}}</style>
<h1>{destination.name}</h1><p><strong>{manifest['evidence_type']} EVIDENCE</strong></p>
<p>Decision: {html.escape(str(metrics.get('status')))} — {html.escape(str(metrics.get('reason')))}</p>
<p>Robust-model inliers are separate from accepted control points. Pixel errors use the named working grid. Ground accuracy and cycle validation are unavailable unless explicitly measured.</p>
<p><a href="manifest.json">Manifest</a> · <a href="config.json">Configuration</a> · <a href="matches.csv">All matches</a> · <a href="inliers.csv">Robust inliers</a> · <a href="transform.json">Transform</a> · <a href="metrics.json">Metrics</a></p>
<h2>Exact-run metrics</h2><pre>{html.escape(json.dumps(metrics,indent=2))}</pre>{''.join(image_links)}</html>'''
    (staging/'report.html').write_text(report)
    manifest['artifact_checksums']={str(p.relative_to(staging)):sha256_file(p) for p in sorted(staging.rglob('*')) if p.is_file()}
    write_json(staging/'manifest.json',manifest)
    # The exclusive staging name prevents two writers from publishing the same ID.
    if destination.exists():
        raise FileExistsError('Destination appeared while staging')
    os.rename(staging,destination)
    for path in destination.rglob('*'):
        if path.is_file():
            path.chmod(0o444)
    return destination
