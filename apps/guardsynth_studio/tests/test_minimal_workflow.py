import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from apps.guardsynth_studio.common import StudioError, uid
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio import sequence
from guard_synth import studio_sequence
from .helpers import fixture, edit, approve
from .test_sequence import CATALOG, condition, scene

class MinimalWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store,self.service,self.ids,self.extraction,self.video,_=fixture(self.temp.name,2)
        self.addCleanup(self.store.close)
    def fill(self,index=0):
        mid=self.ids[index];fid=self.store.moment(mid)['frame']['frame_id']
        c=scene(index)['coc'];c['evidence_refs']=[fid]
        edit(self.service,mid,'sequence_coc',c);approve(self.service,mid,'sequence_coc')
        con=condition(source_refs=[]);con['evidence_refs']=[fid]
        edit(self.service,mid,'sequence_constraints',{'constraints':[con]});approve(self.service,mid,'sequence_constraints')
    def run_stage(self,kind):
        result=sequence.enqueue_stage(self.service,self.extraction,kind,'reviewer',uid())
        Worker(self.service).run_once()
        job=self.store.get(result['job_id'],'job')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        return job
    def test_five_stage_flow_compiles_without_solver_and_verifies_saved_core(self):
        self.assertTrue(hasattr(sequence,'enqueue_stage'),'Separate EBLC, verification and CNL stages required')
        with self.assertRaises(StudioError): sequence.enqueue_stage(self.service,self.extraction,'SEQ_VERIFY','reviewer',uid())
        self.fill(0);self.fill(1)
        with patch('guard_synth.studio_sequence.check_queries',side_effect=AssertionError('Solver belongs in verification')):
            build=self.run_stage('SEQ_EBLC')
        self.assertNotIn('smt',build['result']['scenes'][0])
        self.assertIn('core',build['result']['scenes'][0])
        with self.assertRaises(StudioError): sequence.enqueue_stage(self.service,self.extraction,'SEQ_CNL','reviewer',uid())
        verified=self.run_stage('SEQ_VERIFY')
        self.assertEqual(verified['inputs']['parent_job_id'],build['id'])
        self.assertIn('core',verified['result']['scenes'][0]['verification'])
        self.assertEqual(verified['result']['status'],'REVIEW_REQUIRED')
        cnl=self.run_stage('SEQ_CNL')
        self.assertEqual(cnl['inputs']['parent_job_id'],verified['id'])
        self.assertIn('보행자',cnl['result']['samples'][0]['text'])
        self.assertFalse(cnl['result']['training_eligible'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM metadata WHERE key='openai_calls'").fetchone()[0],0)
    def test_upstream_edit_invalidates_each_derived_stage(self):
        self.assertTrue(hasattr(sequence,'enqueue_stage'),'Explicit server-owned stage artifacts required')
        self.fill();self.run_stage('SEQ_EBLC');self.run_stage('SEQ_VERIFY');self.run_stage('SEQ_CNL')
        edit(self.service,self.ids[0],'sequence_coc',{'explanation':'수정한 설명'})
        stages=sequence.sequence_view(self.service,self.extraction)['stages']
        self.assertTrue(all(stages[k]['stale'] for k in ('eblc','verification','cnl')))
        with self.assertRaises(StudioError): sequence.enqueue_stage(self.service,self.extraction,'SEQ_VERIFY','reviewer',uid())
    def test_edit_during_build_or_parent_replacement_rejects_queued_result(self):
        self.assertTrue(hasattr(sequence,'enqueue_stage'),'Stage results must bind current upstream artifacts')
        self.fill();self.run_stage('SEQ_EBLC')
        queued=sequence.enqueue_stage(self.service,self.extraction,'SEQ_VERIFY','reviewer',uid())
        newer=sequence.enqueue_stage(self.service,self.extraction,'SEQ_EBLC','reviewer',uid())
        Worker(self.service).run_once()
        self.assertEqual(self.store.get(queued['job_id'],'job')['status'],'STALE_RESULT')
        Worker(self.service).run_once()
        self.assertEqual(self.store.get(newer['job_id'],'job')['status'],'SUCCEEDED')
    def test_declared_action_contradiction_survives_separate_compilation(self):
        self.assertTrue(hasattr(studio_sequence,'compile_sequence'),'EBLC compilation must precede solving')
        moments=[scene(0,[condition()]),scene(1,actions=['ENTER'])]
        compiled=studio_sequence.compile_sequence(moments,CATALOG)
        result=studio_sequence.verify_compiled(compiled)
        self.assertIn('ACTION_CONTRADICTION',result['scenes'][1]['codes'])
        self.assertEqual([r["codes"] for r in result["scenes"]],[r["codes"] for r in studio_sequence.verify_sequence(moments,CATALOG)["scenes"]])

    def test_cnl_retains_condition_carried_from_previous_scene(self):
        moments=[scene(0,[condition()]),scene(1,actions=['HOLD'])]
        compiled=studio_sequence.compile_sequence(moments,CATALOG)
        rendered=studio_sequence.render_verified(compiled,studio_sequence.verify_compiled(compiled))
        self.assertIn('보행자',rendered['samples'][1]['text'])
