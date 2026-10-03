import unittest
from src.contract_spans import contract_spans, id_schema, resolve_contract_spans
from src.grounding import grounded_schema
from src.rag_review import OUTPUT_SCHEMA, build_request
from src.comparison_checks import comparison_issue, source_scope_issue
from src.retrieval import query_topics

class ContractSelectionTests(unittest.TestCase):
    def test_rent_without_deduction_is_not_a_deposit(self):
        self.assertEqual(query_topics('Tenant pays rent in advance without deduction or set-off and pays water, electricity, gas and sewerage.'),{'rent','utilities'})
        self.assertIn('security_deposit',query_topics('Landlord may deduct unpaid rent from the security deposit.'))
    def test_exact_ids_without_summarizing(self):
        clause = "The Tenant pays rent. The Landlord shall give fourteen (14) days' written notice."
        spans = contract_spans(clause)
        self.assertEqual(len(spans), 2)
        for text in spans.values(): self.assertIn(text, clause)
        resolved = resolve_contract_spans({'comparisons':[{'contract_span_id':'C002'}]}, clause)
        self.assertEqual(resolved['comparisons'][0]['contract_quote'], spans['C002'])

    def test_long_spans_remain_exact_and_bounded(self):
        clause = ('Tenant shall pay ' * 100) + '.'
        for span in contract_spans(clause).values():
            self.assertLessEqual(len(span), 480)
            self.assertIn(span, clause)

    def test_unknown_and_dual_ids_rejected(self):
        for item in ({'contract_span_id':'C999'}, {'contract_span_id':'C001','contract_quote':'x'}):
            with self.assertRaises(ValueError):
                resolve_contract_spans({'comparisons':[item]}, 'The tenant pays rent.')

    def test_schema_does_not_ask_for_generated_quote(self):
        schema = id_schema(grounded_schema(OUTPUT_SCHEMA))
        props = schema['schema']['properties']['comparisons']['items']['properties']
        self.assertIn('contract_span_id', props)
        self.assertNotIn('contract_quote', props)
        self.assertIn('C001', build_request('HDB','The tenant pays rent.',[])['messages'][1]['content'])

    def test_replenishment_is_not_cure(self):
        self.assertIsNotNone(comparison_issue('review_required',
            'Tenant may have only 7 days to remedy before deduction.',
            'Tenant shall replenish the deposit within seven days.', [], []))

    def test_fee_mechanism_not_covered_by_repair_payer(self):
        self.assertIsNotNone(comparison_issue('no_material_difference_found','Both parties align.',
            'A plumber report is prima facie evidence; cost of such report is paid by the tenant.',
            [{'quote':'The Landlord maintains concealed pipes.'}], []))

    def test_only_at_extension_is_not_exhaustive_evidence(self):
        self.assertIsNotNone(source_scope_issue('The reference allows review only upon extension.',
            [{'quote':'The rent may be reviewed at a mutually agreed rate upon extension.'}]))
