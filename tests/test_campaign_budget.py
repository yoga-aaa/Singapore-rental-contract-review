import json
import tempfile
import unittest
from pathlib import Path
from src.campaign_budget import verify_campaign
from src.frozen_external import byte_hash


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rental-campaign-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.repo=self.root/'repo'; self.repo.mkdir()
        self.path=self.root/'campaign.json'; self.finish=self.root/'previous/run_finished.json'
        self.finish.parent.mkdir()
        self.record={'status':'complete','accounting':{'unaccounted_attempt':False,'cost_usd':'0.7858850'}}
        self.approval={'approved_by':'human_owner','user_authorization_quote':'Synthetic fixture approved for US$3 only',
                       'max_cost_usd':'3','completed_runs':[]}
        self.save()

    def save(self):
        self.finish.write_text(json.dumps(self.record),encoding='utf-8')
        self.approval['completed_runs']=[{'run_finished_path':'previous/run_finished.json','sha256':byte_hash(self.finish)}]
        self.path.write_text(json.dumps(self.approval),encoding='utf-8')

    def test_actual_spend_plus_full_reservation_not_estimated_free_run(self):
        result=verify_campaign(self.path,self.repo,'1')
        self.assertEqual(result['prior_spend_usd'],'0.7858850')
        self.assertEqual(result['remaining_after_reservation_usd'],'1.2141150')

    def test_missing_cap_or_insufficient_budget_blocks(self):
        with self.assertRaisesRegex(ValueError,'cumulative'): verify_campaign(None,self.repo,'1')
        for cap in ['1.5','-1','NaN','Infinity','not-money',None]:
            self.approval['max_cost_usd']=cap; self.save()
            with self.subTest(cap=cap),self.assertRaises(ValueError): verify_campaign(self.path,self.repo,'1')

    def test_unknown_cost_stops_new_run(self):
        self.record['accounting']['unaccounted_attempt']=True; self.save()
        with self.assertRaisesRegex(ValueError,'Unknown charges'): verify_campaign(self.path,self.repo,'1')

    def test_changed_and_duplicate_records_rejected(self):
        self.finish.write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'accounting changed'): verify_campaign(self.path,self.repo,'1')
        self.save()
        self.approval['completed_runs']*=2
        self.path.write_text(json.dumps(self.approval),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicated'): verify_campaign(self.path,self.repo,'1')

    def test_public_campaign_or_cross_root_paths_rejected(self):
        public=self.repo/'campaign.json'; public.write_text(self.path.read_text(),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'public repository'): verify_campaign(public,self.repo,'1')
        self.approval['completed_runs'][0]['run_finished_path']='../elsewhere.json'
        self.path.write_text(json.dumps(self.approval),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'escapes root'): verify_campaign(self.path,self.repo,'1')
