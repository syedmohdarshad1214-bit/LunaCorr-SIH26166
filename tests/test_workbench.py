"""Synthetic end-to-end and boundary tests; no claim of real lunar validation."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from api.app import app
from prepare_pair import native_mapping,prepare
from src.ingest.manifest import sha256_file
from src.ingest.demo_pack import ROOT,create_pack,scene,defaults,write
from src.registration.baseline import run_baseline
from src.verification.cycle import reverse_cycle
from run_demo import execute


class WorkbenchTests(unittest.TestCase):
    def test_independent_reverse_cycle(self):
        a,b,ma,mb,truth=scene('success')
        rows,transform,metrics,_=run_baseline(a,b,ma,mb,defaults(),'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['status'],'REGISTERED')
        self.assertEqual(metrics['cycle_check'],'MEASURED')
        self.assertLess(metrics['cycle_closure_error']['rmse'],.1)
        self.assertGreater(metrics['cycle_closure_error']['reverse_candidates'],100)

    def test_inconsistent_reverse_rejected(self):
        a,b,ma,mb,_=scene('success')
        with patch('src.registration.baseline.reverse_cycle',return_value={'status':'MEASURED','p90':10,'rmse':9}):
            _,transform,m,_=run_baseline(a,b,ma,mb,defaults(),'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(m['status'],'REJECTED (consistency)');self.assertFalse(transform['accepted'])

    def test_dark_and_flat_abstain(self):
        for case,reason in [('shadow','ABSTAIN_SHADOW'),('flat','ABSTAIN_INSUFFICIENT_FEATURES')]:
            a,b,ma,mb,_=scene(case)
            _,_,m,_=run_baseline(a,b,ma,mb,defaults(),'VERIFIED_PIXEL_GEOMETRY')
            self.assertEqual(m['reason'],reason)

    def test_pixel_centres_preserved(self):
        native=from_origin(100,200,5,5);working=from_origin(110,180,10,10)
        expected=np.array([[2,0,2.5],[0,2,4.5],[0,0,1]])
        np.testing.assert_allclose(native_mapping(native,working),expected)

    def test_geotiff_adapter_on_synthetic_files(self):
        # Exercise the real-input adapter using temporary synthetic file fixtures.
        # Never publish this fixture as a real experiment.
        with tempfile.TemporaryDirectory(dir=ROOT/'data/derived') as temp:
            pack=Path(temp)/'input';create_pack(pack)
            records=[]
            for name in ('source','target'):
                science=pack/(name+'.tif')
                values=np.arange(640*640,dtype=np.float32).reshape(640,640)%251+1
                with rasterio.open(science,'w',driver='GTiff',height=640,width=640,count=1,dtype='float32',
                    crs='+proj=laea +lat_0=-69 +lon_0=20 +R=1737400 +units=m',transform=from_origin(-2.5,2.5,5,5)) as ds:ds.write(values,1)
                files={k:str((pack/(name+suffix)).relative_to(ROOT)) for k,suffix in [('science_file','.tif'),('xml_file','.xml'),('browse_file','.png')]}
                records.append(dict(sensor='TMC-2',product_id=name,product_type='SYNTHETIC_TEST_FIXTURE',acquisition_time=None,orbit=None,footprint=None,resolution_m=5,
                    **files,checksum={f:sha256_file(ROOT/f) for f in files.values()},source='synthetic unit test',notes='Temporary synthetic fixture; not real data'))
            review={'classification':'BROWSE VERIFIED','product_ids':['source','target'],'reviewer':'Synthetic fixture test','repeated_structures':'Synthetic fixture only',
                'browse_checksums':{r['browse_file']:r['checksum'][r['browse_file']] for r in records}}
            write(pack/'review.json',review)
            context=json.loads((pack/'context.json').read_text())
            request=dict(product_records=records,orthorectified_reviewed=True,geometry_basis='Synthetic fixture affine camera',browse_review=str((pack/'review.json').relative_to(ROOT)),
                contexts=[context,context],profiles=['geom_vertices','geom_vertices'],bands=[[1],[1]],band_selection_reason='Synthetic single band fixture',
                working_resolution_m=10,search_radius_working_px=24,experiment_id='EXP999999_TEST_TEST')
            result=prepare(request,Path(temp)/'prepared')
            self.assertEqual(result['status'],'PREPARED_REVIEWED_REAL_PAIR')
            with np.load(Path(temp)/'prepared/roi.npz') as bundle:
                self.assertLessEqual(max(bundle['source'].shape),320)
                self.assertGreater(bundle['source_mask'].sum(),1000)

    def test_bad_roi_hash_stops_before_matching(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/derived') as temp:
            pack=Path(temp)/'input';cfg=create_pack(pack)
            cfg['experiment_id']='EXP999999_TEST_TEST';write(pack/'config.json',cfg)
            with (pack/'roi.npz').open('ab') as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):execute(pack/'config.json')

    def test_api_reads_and_guards(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/').status_code,200)
            self.assertEqual(client.get('/api/status').status_code,200)
            self.assertEqual(client.post('/api/run',json={'case':'invented'}).status_code,400)
            self.assertEqual(client.post('/api/run',json={},headers={'Origin':'https://unrelated.example'}).status_code,403)
            self.assertEqual(client.post('/api/import?name=../../bad.xml',content=b'<a/>').status_code,400)
            self.assertEqual(client.post('/api/import?name=bad.xml',content=b'bad xml').status_code,400)
            r=client.post('/api/geometry',json={'source_label':'../outside.xml','target_label':'bad.xml','source_context':{},'target_context':{}})
            self.assertEqual(r.json()['status'],'UNRESOLVED_GEOMETRY')
            folder=ROOT/r.json()['report_path'];folder.unlink();(folder.parent/'request.json').unlink();folder.parent.rmdir()


if __name__=='__main__':unittest.main()
