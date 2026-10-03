import copy
import unittest
from scripts.complete_v18_regression import restore_accounting


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        for i in range(37):
            common={'case_id':f'NEW_{i//2+1:02d}','call_number':i+1}
            self.events.extend([{'event':'attempt',**common,'model':'openai/gpt-4.1' if i%2==0 else 'openai/gpt-4o'},
                                {'event':'response',**common,'body':{'usage':{'prompt_tokens':10,
                                 'completion_tokens':2,'total_tokens':12,'cost':0.001}}}])
        self.finish={'status':'partial_stopped','failure_type':'BudgetStop',
                     'accounting':{'api_calls':37,'prompt_tokens':370,'completion_tokens':74,
                                   'total_tokens':444,'cost_usd':'0.037','unaccounted_attempt':False}}

    def test_reconciles_original_charges_before_any_new_call(self):
        restored=restore_accounting(self.events,self.finish)
        self.assertEqual(restored['totals']['api_calls'],37)
        self.assertEqual(restored['cached_attempt']['case_id'],'NEW_19')

    def test_unknown_provider_error_or_cost_discrepancy_blocks_recovery(self):
        for change in [{'failure_type':'RuntimeError'},{'status':'complete'},
                       {'accounting':{**self.finish['accounting'],'unaccounted_attempt':True}},
                       {'accounting':{**self.finish['accounting'],'cost_usd':'0'}}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                restore_accounting(self.events,{**self.finish,**change})

    def test_duplicate_missing_wrong_case_or_nonfinite_charge_blocked(self):
        variants=[self.events[:-1],self.events+[self.events[-1]]]
        wrong=copy.deepcopy(self.events); wrong[-1]['case_id']='NEW_18'; variants.append(wrong)
        wrong=copy.deepcopy(self.events); wrong[-1]['body']['usage']['cost']='NaN'; variants.append(wrong)
        for variant in variants:
            with self.subTest(length=len(variant)),self.assertRaises(ValueError):
                restore_accounting(variant,self.finish)
