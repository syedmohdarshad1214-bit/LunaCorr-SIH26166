"""SYNTHETIC known-transform and bounded-I/O tests; not real lunar evidence."""

import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from src.registration.baseline import run_baseline
from src.evaluation.experiment import save_experiment
from src.ingest.manifest import sha256_file
from src.ingest.raster import read_window
from src.preprocessing.optical import downsample
from src.verification.robust import verify


def config():
    return dict(source_product_id='SYNTHETIC_SOURCE',target_product_id='SYNTHETIC_TARGET',
        target_working_grid='SYNTHETIC target native 512x512 grid',
        source_working_to_native=np.eye(3).tolist(),target_working_to_native=np.eye(3).tolist(),
        source_to_target_prior=[[1,0,8],[0,1,-5],[0,0,1]],
        normalization_percentiles=[2,98],search_radius_target_working_px=16,
        ratio_filter=.75,matcher='SIFT',max_features=2000,
        robust=dict(models=['translation','similarity','affine'],residual_threshold_px=2,
                    min_inliers=12,min_inlier_ratio=.6,holdout_fraction=.25,min_holdout_inliers=4,
                    min_holdout_ratio=.6,max_holdout_rmse_px=1,seed=7,max_trials=1000),
        coverage_grid_cells=4,min_grid_coverage=.5,min_hull_coverage=.4,require_cycle=False)


def scene():
    rng=np.random.default_rng(19)
    source=cv2.GaussianBlur(rng.integers(0,256,(512,512),dtype=np.uint8),(5,5),0)
    for _ in range(100):
        center=tuple(rng.integers(30,480,2).tolist())
        cv2.circle(source,center,int(rng.integers(3,12)),int(rng.integers(10,245)),2)
    matrix=np.array([[1,0,9],[0,1,-6],[0,0,1]],dtype=float)
    target=cv2.warpPerspective(source,matrix,(512,512))
    mask=np.zeros((512,512),dtype=bool)
    mask[30:-30,30:-30]=True
    return source,target,mask,matrix


class BaselineTests(unittest.TestCase):
    def test_known_translation_and_saved_artifacts(self):
        a,b,mask,truth=scene()
        cfg=config()
        rows,transform,metrics,images=run_baseline(a,b,mask,mask,cfg,'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['status'],'REGISTERED')
        self.assertEqual(transform['model'],'translation')
        np.testing.assert_allclose(np.array(transform['matrix'])[:2,2],truth[:2,2],atol=.25)
        self.assertLess(metrics['heldout_inlier_errors']['rmse'],.5)
        self.assertTrue(any(r['population']=='HELD_OUT' for r in rows))
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'EXP001_TEST_TEST'
            save_experiment(destination,{'evidence_type':'SYNTHETIC'},cfg,rows,transform,metrics,images)
            manifest=json.loads((destination/'manifest.json').read_text())
            for name,digest in manifest['artifact_checksums'].items():
                self.assertEqual(sha256_file(destination/name),digest)
            self.assertIn('SYNTHETIC EVIDENCE',(destination/'report.html').read_text())
            with self.assertRaises(FileExistsError):
                save_experiment(destination,{'evidence_type':'SYNTHETIC'},cfg,rows,transform,metrics)

    def test_akaze_alternative(self):
        a,b,mask,_=scene()
        cfg=config();cfg['matcher']='AKAZE'
        _,_,metrics,_=run_baseline(a,b,mask,mask,cfg,'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['status'],'REGISTERED')

    def test_no_overlap_never_calls_matcher(self):
        a,b,mask,_=scene()
        with patch('src.registration.baseline.bounded_matches',side_effect=AssertionError('must not match')):
            _,_,metrics,_=run_baseline(a,b,mask,mask,config(),'REJECTED (geometry)')
        self.assertEqual(metrics['status'],'REJECTED (geometry)')

    def test_flat_support_abstains(self):
        a=np.zeros((64,64),dtype=np.uint8)
        _,_,metrics,_=run_baseline(a,a,np.ones_like(a,dtype=bool),np.ones_like(a,dtype=bool),config(),'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['reason'],'ABSTAIN_INSUFFICIENT_FEATURES')

    def test_cycle_unavailable_does_not_pass_when_required(self):
        a,b,mask,_=scene();cfg=config();cfg['require_cycle']=True
        _,_,metrics,_=run_baseline(a,b,mask,mask,cfg,'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['reason'],'ABSTAIN_CYCLE_UNAVAILABLE')

    def test_wrong_geometry_prior_does_not_fall_back_global(self):
        a,b,mask,_=scene();cfg=config();cfg['source_to_target_prior'][0][2]=10000
        _,_,metrics,_=run_baseline(a,b,mask,mask,cfg,'VERIFIED_PIXEL_GEOMETRY')
        self.assertEqual(metrics['candidate_count'],0)
        self.assertEqual(metrics['status'],'ABSTAIN')

    def test_outliers_remain_distinct(self):
        rng=np.random.default_rng(2)
        a=rng.uniform(0,500,(100,2));b=a+[9,-6]
        b[-15:]=rng.uniform(0,500,(15,2))
        result=verify(a,b,config()['robust'])
        self.assertEqual(result['model'],'translation')
        self.assertEqual(int(result['inliers'].sum()),85)

    def test_noninteger_pyramid_center_transform(self):
        image=np.ones((71,103),dtype=np.float32)
        out,mask,matrix=downsample(image,np.ones_like(image,dtype=bool),3.3)
        self.assertAlmostEqual(matrix[0,0]*out.shape[1],103)
        self.assertAlmostEqual(matrix[1,1]*out.shape[0],71)
        self.assertTrue(mask.all())


class WindowReaderTests(unittest.TestCase):
    def test_selected_bands_for_each_axis_order(self):
        base=np.arange(4*11*17,dtype=np.int16).reshape(4,11,17)
        names=['Band','Line','Sample']
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            for order in itertools.permutations(range(3)):
                ordered=base.transpose(order).astype('>i2')
                science=directory/'synthetic.img';ordered.tofile(science)
                axes=''.join(f'<Axis_Array><axis_name>{names[i]}</axis_name><elements>{base.shape[i]}</elements><sequence_number>{j+1}</sequence_number></Axis_Array>' for j,i in enumerate(order))
                label=directory/'synthetic.xml'
                label.write_text(f'''<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
                <!-- SYNTHETIC storage fixture -->
                <Identification_Area><logical_identifier>urn:synthetic:reader</logical_identifier></Identification_Area>
                <File_Area_Observational><File><file_name>synthetic.img</file_name></File><Array_3D_Spectrum>
                <offset unit="byte">0</offset><axes>3</axes><axis_index_order>Last Index Fastest</axis_index_order>
                <Element_Array><data_type>SignedMSB2</data_type><scaling_factor>2</scaling_factor><value_offset>3</value_offset></Element_Array>
                {axes}</Array_3D_Spectrum></File_Area_Observational></Product_Observational>''')
                values,valid,metadata=read_window(label,science,[2,3,4,5],[2,0])
                np.testing.assert_array_equal(values,base[[2,0],2:6,3:8]*2+3)
                self.assertTrue(valid.all())
                self.assertFalse(metadata['whole_cube_materialized'])
                with self.assertRaises(ValueError):
                    read_window(label,science,[2,3,4,5],list(range(4)))
                with self.assertRaises(ValueError):
                    read_window(label,science,[2,3,4,5],[1],max_output_bytes=1)


if __name__=='__main__':
    unittest.main()
