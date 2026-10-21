"""Check semantic-loss mathematics and frozen-input information controls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'projects/04-guardsynth-coc/experiments/paper1_external_methods'))
import run_vlm_constraint_baselines as baseline
import run_vlm_generation_budget as generation
import torch


class SemanticLossTests(unittest.TestCase):
    def test_uniform_probabilities_and_multiple_allowed_labels(self):
        logits=torch.zeros(2,4,requires_grad=True)
        allowed=torch.tensor([[True,False,False,False],[True,False,True,False]])
        expected=(torch.log(torch.tensor(4.))+torch.log(torch.tensor(2.)))/2
        self.assertAlmostEqual(baseline.semantic_loss(logits,allowed).item(),expected.item(),places=6)

    def test_gradient_decreases_forbidden_probability(self):
        logits=torch.tensor([[1.,2.,3.,4.]],requires_grad=True)
        allowed=torch.tensor([[True,False,True,False]])
        before=torch.softmax(logits,-1)[~allowed].sum().item()
        loss=baseline.semantic_loss(logits,allowed)
        loss.backward()
        self.assertTrue((logits.grad[~allowed]>0).all())
        after=torch.softmax(logits-.1*logits.grad,-1)[~allowed].sum().item()
        self.assertLess(after,before)

    def test_all_allowed_has_zero_loss_and_gradient(self):
        logits=torch.randn(2,4,requires_grad=True)
        loss=baseline.semantic_loss(logits,torch.ones(2,4,dtype=torch.bool))
        loss.backward()
        self.assertEqual(loss.item(),0.)
        self.assertEqual(logits.grad.abs().sum().item(),0.)

    def test_empty_admissible_set_rejected(self):
        with self.assertRaises(ValueError):
            baseline.semantic_loss(torch.zeros(1,4),torch.zeros(1,4,dtype=torch.bool))

    def test_first_response_token_uses_preceding_logits(self):
        logits=torch.arange(2*5*9).reshape(2,5,9)
        labels=torch.tensor([[-100,-100,-100,4,8],[-100,-100,5,8,-100]])
        selected=baseline.response_label_logits(logits,labels,[1,3,5,7])
        self.assertTrue(torch.equal(selected[0],logits[0,2,[1,3,5,7]]))
        self.assertTrue(torch.equal(selected[1],logits[1,1,[1,3,5,7]]))

    def test_missing_rule_identifiability_ceiling(self):
        rows=[dict(image_sha256='same',prompts={'no_rule':'same','rule':str(i)},target=t)
              for i,t in enumerate(('A','B'))]
        self.assertEqual(baseline.input_audit(rows,'no_rule')['deterministic_accuracy_ceiling'],.5)
        self.assertEqual(baseline.input_audit(rows,'rule')['deterministic_accuracy_ceiling'],1.)

    def test_hold_mask_uses_rule_not_target(self):
        candidates=[dict(label='A',xy_mm=[[0,0],[0,0],[0,0],[300,0],[0,0],[0,0],[500,0]],progress=100),
                    dict(label='B',xy_mm=[[0,0]]*7,progress=50)]
        row=dict(family='position_hold',meta=dict(candidates=candidates,hold_ms=500),target='B')
        self.assertTrue(baseline.rules(row)['A'][0])
        row['meta']['hold_ms']=2000
        self.assertFalse(baseline.rules(row)['A'][0])
        self.assertTrue(baseline.rules(row)['B'][0])

    def test_list_valued_archived_ids_are_preserved(self):
        def cases(family, split, arm):
            return [dict(id=[1,'short'],family=family,task='maximum_speed',scene_id=1,
                         image_sha256='same',target='A',prompt=arm,image=object(),
                         input_id='unused',meta={})]
        with patch.object(baseline.common,'load_cases',side_effect=cases):
            result=baseline.legacy_cases('static','test')
        self.assertEqual(result[0]['id'],'static:[1,"short"]')
        self.assertEqual(result[0]['source_id'],[1,'short'])
        self.assertEqual(result[0]['prompts'],{'rule':'p2','no_rule':'p0'})

    def test_explanation_options_do_not_override_final_answer(self):
        self.assertEqual(generation.parse_final('A is early; B is safe. Final answer: B','ABCD'),'B')
        self.assertEqual(generation.parse_final('Compare A and B.\n**C**','ABCD'),'C')
        self.assertEqual(generation.parse_final('Consider A and B without choosing.','ABCD'),'INVALID')
        self.assertEqual(generation.parse_final('Final answer: D','AB'),'INVALID')


if __name__=='__main__': unittest.main()
