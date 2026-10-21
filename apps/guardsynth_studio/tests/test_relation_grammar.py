"""Typed grammar and immutable CoC entity binding at approval/compile gates."""
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest

from guard_synth.studio_relations import RULES, atom_error, errors
from guard_synth.studio_grounded_sequence import PREDICATES
from guard_synth.studio_sequence import verify_sequence
from apps.guardsynth_studio.common import StudioError, uid
from apps.guardsynth_studio import sequence
from .helpers import fixture, edit, approve
from .test_grounded_sequence import moment, fact


class RelationGrammarTest(unittest.TestCase):
    def test_every_predicate_has_a_signature(self):
        self.assertEqual(set(RULES),set(PREDICATES))
        self.assertEqual(len({r['group'] for r in RULES.values()}),6)

    def test_unary_and_containment_types_do_not_depend_on_truth(self):
        m=moment();m['coc']['entities'][2]['kind']='OBSTACLE'
        for truth in ('TRUE','FALSE','UNKNOWN'):
            m['constraints']['facts']=[fact(truth,predicate='IN',subject='ego',target='e2')]
            self.assertIn('차로',errors(m['constraints'],{'coc':m['coc']})[0]['message'])
        entities={e['entity_id']:e for e in moment()['coc']['entities']}
        self.assertIsNone(atom_error({'predicate':'ZONE_CLOSED','subject_ref':'e2','object_ref':None},entities))
        self.assertIn('비교·적용 대상이 필요하지',atom_error({'predicate':'ZONE_CLOSED','subject_ref':'e2','object_ref':'ego'},entities))

    def test_adjacency_is_symmetric_without_requiring_reverse_input(self):
        m=moment(definitions=[],facts=[fact(predicate='ADJACENT_TO',subject='e1',target='e2')])
        self.assertEqual(verify_sequence([m],{'sources':[]})['scenes'][0]['verification']['relation_checks']['results'][0]['status'],'SAT')
        m['constraints']['facts'].append(fact('FALSE',predicate='ADJACENT_TO',subject='e2',target='e1'))
        self.assertIn('RELATION_CONTRADICTION',verify_sequence([m],{'sources':[]})['scenes'][0]['codes'])


class RelationApprovalTest(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.store,self.service,self.ids,self.extraction,*_=fixture(temp.name,2);self.addCleanup(self.store.close)
        self.m=moment();fid=self.store.moment(self.ids[0])['frame']['frame_id']
        for e in self.m['coc']['entities']:e['evidence_refs']=[fid]
        self.m['coc']['evidence_refs']=[fid];self.m['coc']['observed_actions'][0]['evidence_refs']=[fid]
        self.m['constraints']['facts'][0]['evidence_refs']=[fid]
        edit(self.service,self.ids[0],'sequence_coc',self.m['coc']);approve(self.service,self.ids[0],'sequence_coc')

    def test_invalid_legacy_draft_can_be_repaired_but_not_approved(self):
        bundle=self.m['constraints'];bundle['facts'][0]['atom']={'predicate':'ZONE_CLOSED','subject_ref':'e2','object_ref':'ego'}
        edit(self.service,self.ids[0],'sequence_constraints',bundle)
        with self.assertRaises(StudioError) as raised:approve(self.service,self.ids[0],'sequence_constraints')
        self.assertEqual(raised.exception.code,'RELATION_FORMAT')
        bundle['facts'][0]['atom']['object_ref']=None
        edit(self.service,self.ids[0],'sequence_constraints',bundle);approve(self.service,self.ids[0],'sequence_constraints')

    def test_same_kind_entity_rename_cannot_be_rebound_by_saving(self):
        edit(self.service,self.ids[0],'sequence_constraints',self.m['constraints']);approve(self.service,self.ids[0],'sequence_constraints')
        old=deepcopy(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['entity_binding'])
        self.m['coc']['entities'][2]['description']='이전과 다른 진입 구역'
        edit(self.service,self.ids[0],'sequence_coc',self.m['coc']);approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',self.m['constraints'])
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['entity_binding'],old)
        with self.assertRaises(StudioError) as raised:approve(self.service,self.ids[0],'sequence_constraints')
        self.assertEqual(raised.exception.code,'CONSTRAINT_ENTITY_BINDING')
        self.assertTrue(sequence.input_diagnostics(self.service,self.store.moment(self.ids[0]))['constraint_binding'])

    def test_previously_approved_invalid_pair_cannot_reach_smt(self):
        edit(self.service,self.ids[0],'sequence_constraints',self.m['constraints']);approve(self.service,self.ids[0],'sequence_constraints')
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);m['components']['sequence_constraints']['payload']['facts'][0]['atom']['object_ref']='e1'
            self.store.save(m,'historical invalid approval fixture')
        with self.assertRaises(StudioError) as raised:sequence.enqueue_stage(self.service,self.extraction,'SEQ_EBLC','reviewer',uid())
        self.assertEqual(raised.exception.code,'RELATION_FORMAT')
        self.assertEqual(self.store.objects('job'),[])

    def test_explanation_change_keeps_valid_entity_binding(self):
        edit(self.service,self.ids[0],'sequence_constraints',self.m['constraints']);approve(self.service,self.ids[0],'sequence_constraints')
        self.m['coc']['explanation']='영상에 맞춰 설명 문장만 수정'
        edit(self.service,self.ids[0],'sequence_coc',self.m['coc']);approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',self.m['constraints']);approve(self.service,self.ids[0],'sequence_constraints')
        self.assertIsNone(sequence.constraint_binding_issue(self.service,self.store.moment(self.ids[0])))

    def test_close_waits_for_active_query(self):
        import threading
        entered=threading.Event();finished=threading.Event()
        def close():
            entered.set();self.store.close();finished.set()
        with self.store.lock:
            thread=threading.Thread(target=close);thread.start();entered.wait(1)
            self.assertFalse(finished.wait(.05))
            self.assertEqual(self.store.db.execute('SELECT 1').fetchone()[0],1)
        thread.join(1);self.assertTrue(finished.is_set())

    def test_annotation_read_waits_for_transaction(self):
        import threading
        entered=threading.Event();finished=threading.Event();read=[]
        def reader():
            entered.set();read.append(self.store.moment(self.ids[0]));finished.set()
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);updated=self.store.save(m,'concurrent review fixture')
            thread=threading.Thread(target=reader);thread.start();entered.wait(1)
            self.assertFalse(finished.wait(.05))
        thread.join(1);self.assertTrue(finished.is_set());self.assertEqual(read[0]['revision'],updated['revision'])
