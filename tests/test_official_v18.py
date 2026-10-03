import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.official_sources import article_text, sections, article_digest, digest, HOSTS
from src.evidence_packet_v18 import PacketRetriever, web_eligible
from src.review_v18 import build_request, finalize, obligation_inventory, shape_issue
from src.application import Clause, run_document

ROOT = Path(__file__).resolve().parents[1]


def ref(text='The tenant pays utilities.',topic='utilities',kind='tenancy_agreement_template',housing='HDB'):
    return {'source_id':'TEST','housing_type':housing,'source_kind':kind,'title':'Synthetic reference fixture',
            'page_number':1,'section':'Fixture only','text':text,'topics':[topic],
            'evidence_id':'R001','url':'','source_sha256':''}


def row(clause,topic='utilities',relation='equivalent'):
    return {'contract_span_ids':['C001'],'obligation_ids':list(obligation_inventory(clause)),
            'reference_ids':['R001'],'topic':topic,'relation':relation,
            'reference_claim':'The tenant pays utilities.','difference':'The utility payer is the same.',
            'tenant_consequence':'','question':'','verdict':'supported','check_note':'The actor and utility-payment duty match the cited fixture.'}


class AtomicTests(unittest.TestCase):
    def setUp(self):
        self.clause='The tenant pays utilities.'
        self.packet={'references':[ref()],'truncated':False,'topics':['utilities']}
        self.raw={'comparisons':[row(self.clause)],'unassessed_span_ids':[]}

    def test_complete_equivalent_fixture_passes(self):
        self.assertEqual(finalize(self.raw,self.clause,self.packet,'HDB').label,'no_material_difference_found')

    def test_unknown_reference_id_abstains(self):
        self.raw['comparisons'][0]['reference_ids']=['R999']
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_wrong_housing_abstains(self):
        self.packet['references'][0]['housing_type']='Private Residential'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_wrong_topic_abstains(self):
        self.packet['references'][0]['topics']=['rent']
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_tax_cannot_prove_utilities(self):
        self.packet['references'][0]['source_kind']='stamp_duty_guidance'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_agent_scheme_cannot_prove_tenancy_fee(self):
        self.packet['references'][0]['source_kind']='agent_dispute_route_guidance'
        self.raw['comparisons'][0]['topic']='dispute_resolution'
        self.packet['references'][0]['topics']=['dispute_resolution']
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_truncated_packet_cannot_pass(self):
        self.packet['truncated']=True
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_uncertain_comparison_cannot_pass(self):
        self.raw['comparisons'][0]['verdict']='uncertain'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_unsupported_comparison_cannot_pass(self):
        self.raw['comparisons'][0]['verdict']='unsupported'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_uncovered_second_sentence_cannot_pass(self):
        clause=self.clause+' An independent surveyor report is final and binding and the tenant pays its fees.'
        self.assertTrue(finalize(self.raw,clause,self.packet,'HDB').abstained)

    def test_uncovered_mechanism_in_same_sentence_cannot_pass(self):
        clause='The tenant pays utilities and an expert report fee.'
        one=row(clause); one['obligation_ids']=['A001']
        raw={'comparisons':[one],'unassessed_span_ids':[]}
        self.assertGreater(len(obligation_inventory(clause)),1)
        self.assertTrue(finalize(raw,clause,self.packet,'HDB').abstained)

    def test_supported_limited_risk_does_not_approve_other_terms(self):
        clause='The tenant pays utilities and a late charge. Another obligation is unclear.'
        adverse=row(clause,relation='tenant_adverse')
        adverse['obligation_ids']=['A001']; adverse['tenant_consequence']='A specific additional late-payment amount may be charged.'
        adverse['difference']='The contract adds a stated late utility charge.'
        self.packet['references'][0]['text']='The tenant pays actual utility charges with no additional late-payment fee.'
        adverse['reference_claim']='The tenant pays actual utility charges with no additional late-payment fee.'
        adverse['question']='Can the additional late-payment charge be clarified?'
        result=finalize({'comparisons':[adverse],'unassessed_span_ids':['C002']},clause,self.packet,'HDB')
        self.assertEqual(result.label,'review_required')
        self.assertIn('other terms are not approved',result.reason)
        self.assertIn('C002',result.comparisons[0]['unassessed_span_ids'])

    def test_omission_cannot_become_risk(self):
        one=self.raw['comparisons'][0]
        one.update(relation='tenant_adverse',difference='The contract omits prior notice.',tenant_consequence='There is no notice before the landlord deducts.',question='Can the missing notice be restored?')
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_invented_reference_number_abstains(self):
        self.raw['comparisons'][0]['reference_claim']='The tenant pays utilities within 7 days.'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_number_substring_is_not_support(self):
        self.packet['references'][0]['text']='The tenant pays utilities within 14 days.'
        self.raw['comparisons'][0]['reference_claim']='The tenant pays utilities within 1 day.'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_reference_silence_cannot_prove_rule(self):
        self.raw['comparisons'][0]['reference_claim']='The template does not mention utility fees.'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_legal_verdict_abstains(self):
        self.raw['comparisons'][0]['difference']='The payment term is illegal.'
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_malformed_verdict_fails_closed(self):
        self.raw['comparisons'][0]['verdict']=[]
        self.assertTrue(finalize(self.raw,self.clause,self.packet,'HDB').abstained)

    def test_dynamic_ids_and_full_verifier_packet(self):
        draft={k:v for k,v in self.raw.items()}
        request=build_request('HDB',self.clause,self.packet,draft)
        properties=request['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        self.assertEqual(properties['reference_ids']['items']['enum'],['R001'])
        self.assertEqual(properties['contract_span_ids']['items']['enum'],['C001'])
        data=json.loads(request['messages'][1]['content'])
        self.assertIn('untrusted_reference_packet',data)
        self.assertIn('obligations',data['untrusted_reference_packet'])
        self.assertEqual(request['model'],'openai/gpt-4o')

    def test_binding_does_not_generate_or_shorten_quote(self):
        result=finalize(self.raw,self.clause,self.packet,'HDB')
        self.assertEqual(result.evidence[0]['quote'],self.packet['references'][0]['text'])
        self.assertEqual(result.comparisons[0]['contract_quote'],self.clause)


class ScopeTests(unittest.TestCase):
    def test_only_stamp_query_retrieves_iras(self):
        source=ref(topic='stamp_duty',kind='stamp_duty_guidance',housing='Both')
        self.assertTrue(web_eligible(source,'The tenant pays stamp duty.','HDB'))
        self.assertFalse(web_eligible(source,'The tenant pays utility charges.','HDB'))

    def test_agent_scheme_not_for_landlord_dispute(self):
        source=ref(topic='agent_dispute',kind='agent_dispute_route_guidance',housing='Both')
        self.assertFalse(web_eligible(source,'The landlord and tenant dispute a deduction.','HDB'))
        self.assertTrue(web_eligible(source,'A property agency commission dispute under the estate agency agreement.','HDB'))

    def test_courts_not_for_report_fee_fairness(self):
        source=ref(kind='dispute_route_guidance',housing='Both')
        self.assertFalse(web_eligible(source,'The tenant pays the plumber report fee.','HDB'))
        self.assertTrue(web_eligible(source,'A small claim in the tribunal.','HDB'))

    def test_housing_domains_do_not_mix(self):
        source={**ref(kind='housing_policy_background'),'source_id':'HDB_RENTAL_REGULATIONS'}
        self.assertFalse(web_eligible(source,'The tenant may sublet.','Private Residential'))

    def test_empty_shell_not_evidence(self):
        with self.assertRaises(ValueError):
            article_text(b'<html><title>Official title</title><main><h1>Heading only</h1></main></html>',{'authority':'URA'})


@unittest.skipUnless((ROOT/'data/official_sources_v18/index_v18.jsonl').exists(),'Run bootstrap_official_v18.py for official-source integration tests')
class OfficialIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.retriever=PacketRetriever.from_repo(ROOT)

    def test_seven_sources_loaded_and_scope_kept(self):
        self.assertEqual(len({r['source_id'] for r in self.retriever.official}),7)
        self.assertEqual(len(self.retriever.official),49)

    def test_hdb_sublet_packet_has_prohibition_and_actors(self):
        packet=self.retriever.packet('The tenant may sublet with written landlord consent.','HDB')
        body=' '.join(r['text'] for r in packet['references'] if r['source_kind']=='housing_policy_background')
        self.assertIn('do not further rent out',body)
        self.assertIn('Flat owners',body)

    def test_ura_relaxation_keeps_dates_area_registration(self):
        packet=self.retriever.packet('Eight unrelated occupants may live in the private property.','Private Residential')
        body=' '.join(r['text'] for r in packet['references'] if r['source_id']=='URA_RENTING_PROPERTY')
        for condition in ['90sqm','31 Dec 2028','register','same family unit']:
            self.assertIn(condition,body)

    def test_deposit_packet_includes_separate_handover_and_dispute(self):
        packet=self.retriever.packet('After refund the landlord can claim damages, determined by a binding surveyor.','HDB')
        ids={r.get('clause_id') for r in packet['references']}
        self.assertTrue({'2.2','5.4','12.2'}.issubset(ids))

    def test_stamp_only_does_not_include_irrelevant_cea(self):
        packet=self.retriever.packet('The tenant pays stamp duty.','Private Residential')
        self.assertTrue(packet['references'])
        self.assertTrue(all(r['source_kind']=='stamp_duty_guidance' for r in packet['references']))

    def test_application_v18_offline_never_calls_or_reads_key(self):
        with patch('src.application.local_api_key',side_effect=AssertionError('no key')),patch('src.review_v18._request_openrouter',side_effect=AssertionError('no API')):
            result=run_document([Clause('C',(),'The tenant pays stamp duty.')],'Private Residential',
                                synthetic_confirmed=True,extraction_confirmed=True,review_version='v18')
        self.assertEqual(result['accounting']['api_calls'],0)
        self.assertEqual(result['version'],'v18')
        self.assertTrue(result['clauses'][0]['retrieved_sources'])
        self.assertIn('Unmeasured',result['evaluation_status'])

    def test_v18_ui_example_shows_source_locations_without_api(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Install requirements for UI test')
        app=AppTest.from_file(str(ROOT/'app.py')).run()
        app.selectbox(key='evidence_version').set_value('v18 — expanded official sources (unmeasured)').run()
        app.text_area[0].set_value("The Tenant may sublet the flat with the Landlord's written consent and register the arrangement with HDB within seven days.")
        app.checkbox(key='synthetic').check(); app.checkbox(key='extraction_checked').check(); app.run()
        app.button(key='review').click().run()
        self.assertEqual(len(app.exception),0)
        report=app.session_state['report']
        self.assertEqual(report['version'],'v18')
        self.assertEqual(report['accounting']['api_calls'],0)
        self.assertTrue(any(r['source_id'].startswith('HDB_') for r in report['clauses'][0]['retrieved_sources']))
