"""Regeneration invalidation and constraint wire schema regressions."""
from copy import deepcopy
import unittest

from apps.guardsynth_studio import sequence
from apps.guardsynth_studio.common import StudioError, uid
from apps.guardsynth_studio.jobs import Worker
from . import test_grounded_workflow as grounded
from . import test_openai_provider as providers
from .helpers import edit, approve


class GenerationResetTest(unittest.TestCase):
    setUp=grounded.GroundedProviderTest.setUp
    rich=grounded.GroundedProviderTest.rich
    run_job=grounded.GroundedProviderTest.run_job
    generate_pair=grounded.GroundedProviderTest.generate_pair

    def connect(self):
        providers.OpenAIProviderTests.connect(self,{**providers.config(),'max_calls':20})

    def reviewed_pipeline(self):
        self.generate_pair()
        edit(self.service,self.ids[6],'sequence_constraints',{'accepted_unchanged':True})
        approve(self.service,self.ids[6],'sequence_constraints')
        jobs=[]
        for kind in ('SEQ_EBLC','SEQ_VERIFY','SEQ_CNL'):
            queued=sequence.enqueue_stage(self.service,self.extraction,kind,'reviewer',uid())
            Worker(self.service).run_once();job=self.store.get(queued['job_id'],'job')
            self.assertEqual(job['status'],'SUCCEEDED',job.get('error'));jobs.append(job)
        return jobs

    def test_same_entities_regeneration_requires_every_downstream_stage_again(self):
        stages=self.reviewed_pipeline();before=self.store.moment(self.ids[6])
        self.reply=providers.response(self.rich()['coc']);job=self.run_job('SEQ_COC')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        after=self.store.moment(self.ids[6])
        self.assertNotIn('sequence_constraints',after['components'])
        self.assertNotIn('sequence_constraints',after['approvals'])
        self.assertFalse(self.store.approved(after,'sequence_coc'))
        self.assertEqual(self.store.moment(self.ids[6],before['revision']),before)
        for stage in stages:self.assertFalse(sequence.stage_current(self.service,stage))
        with self.assertRaises(StudioError):
            sequence.enqueue_stage(self.service,self.extraction,'SEQ_EBLC','reviewer',uid())
        edit(self.service,self.ids[6],'sequence_coc',{'accepted_unchanged':True})
        approve(self.service,self.ids[6],'sequence_coc')
        self.reply=providers.response(self.rich()['constraints'])
        self.assertEqual(self.run_job('SEQ_CONSTRAINTS')['status'],'SUCCEEDED')
        edit(self.service,self.ids[6],'sequence_constraints',{'accepted_unchanged':True})
        approve(self.service,self.ids[6],'sequence_constraints')
        for kind in ('SEQ_EBLC','SEQ_VERIFY','SEQ_CNL'):
            queued=sequence.enqueue_stage(self.service,self.extraction,kind,'reviewer',uid())
            Worker(self.service).run_once();fresh=self.store.get(queued['job_id'],'job')
            self.assertEqual(fresh['status'],'SUCCEEDED',fresh.get('error'))
            self.assertTrue(sequence.stage_current(self.service,fresh))

    def test_removed_target_id_is_not_reused_by_new_constraints(self):
        self.connect();value=self.rich()
        value['coc']['entities'].append({**deepcopy(value['coc']['entities'][2]),'entity_id':'e4'})
        value['constraints']['new_definitions'][0]['condition_target_refs']=['e2','e4']
        for kind,key in [('SEQ_COC','coc'),('SEQ_CONSTRAINTS','constraints')]:
            self.reply=providers.response(value[key]);self.assertEqual(self.run_job(kind)['status'],'SUCCEEDED')
            edit(self.service,self.ids[6],sequence.KINDS[kind],{'accepted_unchanged':True})
            approve(self.service,self.ids[6],sequence.KINDS[kind])
        old=self.store.moment(self.ids[6])
        self.reply=providers.response(self.rich()['coc']);self.assertEqual(self.run_job('SEQ_COC')['status'],'SUCCEEDED')
        edit(self.service,self.ids[6],'sequence_coc',{'accepted_unchanged':True});approve(self.service,self.ids[6],'sequence_coc')
        # Replay an old browser write: revision CAS, rather than enum failure.
        with self.assertRaises(StudioError) as raised:
            self.service.edit(self.ids[6],old['revision'],'sequence_constraints',value['constraints'],'reviewer',uid())
        self.assertEqual(raised.exception.code,'REVISION_CONFLICT')
        self.reply=providers.response(self.rich()['constraints'])
        self.assertEqual(self.run_job('SEQ_CONSTRAINTS')['status'],'SUCCEEDED')
        wire=self.sent[-1]['text']['format']['schema']['properties']
        refs=wire['new_definitions']['items']['properties']['condition_target_refs']['items']['enum']
        self.assertNotIn('e4',refs)

    def test_historical_generation_cannot_be_saved_even_if_dependencies_rebound(self):
        self.generate_pair();old=deepcopy(self.store.moment(self.ids[6])['components']['sequence_constraints']['payload'])
        self.reply=providers.response(self.rich()['coc']);self.assertEqual(self.run_job('SEQ_COC')['status'],'SUCCEEDED')
        with self.store.transaction():
            m=self.store.moment(self.ids[6]);self.store.install(m,'sequence_constraints',old);self.store.save(m,'historical fixture')
        diagnostics=sequence.input_diagnostics(self.service,self.store.moment(self.ids[6]))
        self.assertIn('새로 생성',diagnostics['constraint_generation'])
        with self.assertRaises(StudioError) as raised:edit(self.service,self.ids[6],'sequence_constraints',{'accepted_unchanged':True})
        self.assertEqual(raised.exception.code,'CONSTRAINT_GENERATION')

    def test_failed_coc_regeneration_preserves_entire_current_pipeline(self):
        stages=self.reviewed_pipeline();before=deepcopy(self.store.moment(self.ids[6]))
        self.reply=TimeoutError();self.assertEqual(self.run_job('SEQ_COC')['status'],'TIMED_OUT')
        self.assertEqual(self.store.moment(self.ids[6]),before)
        for stage in stages:self.assertTrue(sequence.stage_current(self.service,stage))

    def test_late_generation_does_not_remove_newer_reviewed_constraints(self):
        self.reviewed_pipeline();before=self.store.moment(self.ids[6])
        def transport(body,timeout):
            edit(self.service,self.ids[6],'sequence_coc',{'explanation':'생성 중 사람이 수정한 설명'})
            return providers.response(self.rich()['coc'])
        self.service.provider.transport=transport
        job=self.run_job('SEQ_COC');self.assertEqual(job['status'],'STALE_RESULT')
        after=self.store.moment(self.ids[6])
        self.assertEqual(after['components']['sequence_constraints']['id'],before['components']['sequence_constraints']['id'])
        self.assertEqual(after['components']['sequence_coc']['payload']['explanation'],'생성 중 사람이 수정한 설명')

    def test_wire_atoms_offer_only_typed_supplied_ids(self):
        self.generate_pair();schema=self.sent[-1]['text']['format']['schema'];wire=schema['properties']
        atom=schema['$defs']['relation_atom'];reference={'$ref':'#/$defs/relation_atom'}
        self.assertEqual(wire['facts']['items']['properties']['atom'],reference)
        branches={b['properties']['predicate']['enum'][0]:b['properties'] for b in atom['anyOf']}
        self.assertEqual(branches['ZONE_CLOSED']['object_ref'],{'type':'null'})
        self.assertNotIn('ego',branches['IN']['object_ref']['enum'])
        self.assertNotIn('SIGNAL_RED',branches)
        for field in ('activation_all_of','release_any_of','preconditions','expected_postconditions'):
            self.assertEqual(wire['new_definitions']['items']['properties'][field]['items']['properties']['atom'],reference)
