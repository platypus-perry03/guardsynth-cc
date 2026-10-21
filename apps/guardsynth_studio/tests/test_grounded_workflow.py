"""Bounded generation and independently persisted original quality."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
import unittest

from .helpers import fixture, edit, approve
from .test_sequence import scene
from . import test_openai_provider as providers
from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio.sequence import generation_context, sequence_view


class GroundedWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store, self.service, self.ids, self.extraction, self.video, _ = fixture(self.temp.name, 10)
        self.addCleanup(self.store.close)

    def test_eblc_keeps_legacy_seven_frame_evidence_without_regenerating(self):
        from .test_sequence import condition
        from apps.guardsynth_studio.sequence import check_inputs, snapshot, enqueue_stage
        index=6
        m=self.store.moment(self.ids[index])
        frames=self.service.causal_frames(m)
        coc=scene(index)['coc'];coc['evidence_refs']=[f['frame_id'] for f in frames]
        constraints={'constraints':[condition(source_refs=[],evidence_refs=[frames[0]['frame_id']])]}
        edit(self.service,m['id'],'sequence_coc',coc);approve(self.service,m['id'],'sequence_coc')
        edit(self.service,m['id'],'sequence_constraints',constraints);approve(self.service,m['id'],'sequence_constraints')
        original=deepcopy(self.store.moment(m['id'])['components'])
        inputs=check_inputs(self.service,snapshot(self.service,self.extraction))
        self.assertEqual(inputs[index]['frame_ids'],[f['frame_id'] for f in frames])
        queued=enqueue_stage(self.service,self.extraction,'SEQ_EBLC','reviewer',uid())
        Worker(self.service).run_once()
        job=self.store.get(queued['job_id'],'job')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        self.assertEqual(self.store.moment(m['id'])['components'],original)
        self.assertEqual(len(self.store.objects('job')),1)
        self.assertEqual(self.store.db.execute("select count(*) from metadata where key='openai_calls'").fetchone()[0],0)

    def test_modern_eblc_still_limits_evidence_to_previous_and_current(self):
        from .test_grounded_sequence import moment
        from apps.guardsynth_studio.sequence import check_inputs,snapshot
        index=6;value=moment(index);m=self.store.moment(self.ids[index]);fid=m['frame']['frame_id']
        for entity in value['coc']['entities']:entity['evidence_refs']=[fid]
        value['coc']['evidence_refs']=[fid]
        for action in value['coc']['observed_actions']:action['evidence_refs']=[fid]
        for f in value['constraints']['facts']:f['evidence_refs']=[fid]
        edit(self.service,m['id'],'sequence_coc',value['coc'])
        edit(self.service,m['id'],'sequence_constraints',value['constraints'])
        inputs=check_inputs(self.service,snapshot(self.service,self.extraction))
        self.assertEqual(inputs[index]['frame_ids'],[self.store.moment(self.ids[5])['frame']['frame_id'],fid])

    def test_legacy_eblc_evidence_window_keeps_causal_can_and_rejects_invalid_ids(self):
        from apps.guardsynth_studio.sequence import check_inputs,snapshot
        from guard_synth.studio_sequence import compile_sequence
        self.service.attach_vehicle_state(self.video,0,providers.OpenAIProviderTests.vehicle_state(self),'reviewer',uid())
        inputs=check_inputs(self.service,snapshot(self.service,self.extraction))
        m=inputs[6];m['coc']=scene(6)['coc'];m['coc']['evidence_refs']=['CAN:0']
        self.assertIn('CAN:0',m['frame_ids'])
        self.assertNotIn('CAN:6500000',m['frame_ids'])
        self.assertEqual(len(compile_sequence(inputs,{'sources':[]})['scenes']),10)
        for invalid in [self.store.moment(self.ids[7])['frame']['frame_id'],'CAN:6500000','not_a_frame']:
            bad=deepcopy(inputs);bad[6]['coc']['evidence_refs']=[invalid]
            with self.assertRaisesRegex(ValueError,'supplied causal frame IDs'):
                compile_sequence(bad,{'sources':[]})

    def test_generation_manifest_and_can_use_only_previous_and_current(self):
        class Capture:
            mode = 'MOCK'; model = 'test'
            def generate(inner, task, frames, prompt, schema, limits):
                inner.frames, inner.prompt = frames, prompt
                value = scene(6)['coc']; value['evidence_refs'] = [frames[-1]['frame_id']]
                return {'parsed_candidate': value, 'raw_output': value, 'model_version': 'test', 'provider_request_id': 'test'}
        capture = Capture(); self.service.provider = capture
        job = self.service.enqueue(self.ids[6], 0, 'SEQ_COC', 'reviewer', uid())
        queued = self.store.get(job['job_id'], 'job')
        self.assertEqual([f['timestamp_us'] for f in queued['inputs']['frames']], [5000000, 6000000])
        self.assertIn('context_token', queued['inputs'])
        Worker(self.service).run_once()
        self.assertEqual([f['timestamp_us'] for f in capture.frames], [5000000, 6000000])
        self.assertEqual(capture.prompt['sequence_context']['previous_entities'], [])

    def test_previous_approved_coc_is_local_and_late_changes_invalidate_current(self):
        for i in [0, 5]:
            value = scene(i)['coc']; value['evidence_refs'] = [self.store.moment(self.ids[i])['frame']['frame_id']]
            edit(self.service, self.ids[i], 'sequence_coc', value); approve(self.service, self.ids[i], 'sequence_coc')
        context, token = generation_context(self.service, self.store.moment(self.ids[6]))
        self.assertEqual(context['previous_coc']['explanation'], '보행자 때문에 대기함')
        self.assertEqual(context['previous_moment_id'], self.ids[5])
        value = scene(6)['coc']; value['evidence_refs'] = [self.store.moment(self.ids[6])['frame']['frame_id']]
        edit(self.service, self.ids[6], 'sequence_coc', value); approve(self.service, self.ids[6], 'sequence_coc')
        edit(self.service, self.ids[5], 'sequence_coc', {'explanation': '늦은 교정'})
        current = self.service.moment(self.ids[6])
        self.assertTrue(current['components']['sequence_coc']['stale'])
        self.assertNotEqual(token, generation_context(self.service, self.store.moment(self.ids[6]))[1])

    def test_missing_previous_approval_does_not_block_local_generation(self):
        context, _ = generation_context(self.service, self.store.moment(self.ids[6]))
        self.assertEqual(context['previous_entities'], [])
        self.assertEqual(context['known_conditions'], [])

    def test_manual_annotations_report_missing_generated_coverage(self):
        value = scene(0)['coc']; value['evidence_refs'] = [self.store.moment(self.ids[0])['frame']['frame_id']]
        edit(self.service, self.ids[0], 'sequence_coc', value)
        view = sequence_view(self.service, self.extraction)
        self.assertEqual(view['quality']['first_pass']['total'], 0)
        self.assertEqual(view['quality']['not_generated'], 10)
        self.assertEqual(view['quality']['first_pass']['pass'], 0)
        self.assertEqual(view['quality']['first_pass']['review_required'], 0)
        self.assertEqual(view['quality']['first_pass']['pass_rate'], 0)


class GroundedProviderTest(unittest.TestCase):
    def test_invalid_relation_output_is_preserved_but_never_installed(self):
        self.connect();value=self.rich()
        self.reply=providers.response(value['coc'])
        self.assertEqual(self.run_job('SEQ_COC')['status'],'SUCCEEDED')
        edit(self.service,self.ids[6],'sequence_coc',{'accepted_unchanged':True})
        approve(self.service,self.ids[6],'sequence_coc')
        before=deepcopy(self.store.moment(self.ids[6]))
        value['constraints']['facts'][0]['atom']={'predicate':'ZONE_CLOSED','subject_ref':'e2','object_ref':'ego'}
        self.reply=providers.response(value['constraints']);job=self.run_job('SEQ_CONSTRAINTS')
        self.assertEqual(job['status'],'FAILED')
        self.assertEqual(job['error']['code'],'PROVIDER_RELATION_FORMAT')
        self.assertEqual(self.store.moment(self.ids[6])['components'],before['components'])
        self.assertEqual(self.store.objects('model_output')[-1]['code'],'PROVIDER_RELATION_FORMAT')

    setUp = providers.OpenAIProviderTests.setUp
    connect = providers.OpenAIProviderTests.connect
    run_job = providers.OpenAIProviderTests.run_job

    def test_legacy_coc_blocks_constraints_before_job_and_paid_call(self):
        from apps.guardsynth_studio.common import StudioError
        self.connect()
        value=scene(6)['coc'];value['evidence_refs']=[self.store.moment(self.ids[6])['frame']['frame_id']]
        edit(self.service,self.ids[6],'sequence_coc',value);approve(self.service,self.ids[6],'sequence_coc')
        before=deepcopy(self.store.moment(self.ids[6]));jobs=self.store.objects('job')
        for entities in [None,[]]:
            if entities is not None:
                value.update(entities=entities,relations=[],observed_actions=[],unknowns=[])
                edit(self.service,self.ids[6],'sequence_coc',value);approve(self.service,self.ids[6],'sequence_coc')
                before=deepcopy(self.store.moment(self.ids[6]))
            with self.assertRaises(StudioError) as raised:
                self.service.enqueue(self.ids[6],before['revision'],'SEQ_CONSTRAINTS','reviewer',uid())
            self.assertEqual(raised.exception.code,'SEQUENCE_FORMAT')
            self.assertEqual(self.store.objects('job'),jobs)
            self.assertEqual(self.store.moment(self.ids[6]),before)
        self.assertEqual(self.sent,[])
        self.assertIsNone(self.store.db.execute("SELECT value FROM metadata WHERE key='openai_calls'").fetchone())

    def test_modern_constraints_on_legacy_coc_cannot_be_approved(self):
        from apps.guardsynth_studio.common import StudioError
        self.connect()
        value=scene(6)['coc'];value['evidence_refs']=[self.store.moment(self.ids[6])['frame']['frame_id']]
        edit(self.service,self.ids[6],'sequence_coc',value);approve(self.service,self.ids[6],'sequence_coc')
        edit(self.service,self.ids[6],'sequence_constraints',{'new_definitions':[],'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]})
        with self.assertRaises(StudioError) as raised: approve(self.service,self.ids[6],'sequence_constraints')
        self.assertEqual(raised.exception.code,'SEQUENCE_FORMAT')
        self.assertEqual(self.sent,[])

    def rich(self, index=6, action="ENTER"):
        from .test_grounded_sequence import moment
        value=moment(index, action=action, target="e2")
        value["coc"].update(reason_bindings=[],action_observation_complete=False)
        for d in value["constraints"]["new_definitions"]:d["postcondition_window"]="UNSPECIFIED"
        for entity in value["coc"]["entities"]:
            entity.update(identity_status="NEW_LOCAL",previous_entity_ref=None)
        fid=self.store.moment(self.ids[index])["frame"]["frame_id"]
        def evidence(data):
            if isinstance(data,dict):
                for key,val in data.items():
                    if key=="evidence_refs": data[key]=[fid]
                    else: evidence(val)
            elif isinstance(data,list):
                for item in data: evidence(item)
        evidence(value)
        return value

    def generate_pair(self, index=6, action="ENTER"):
        self.connect(); value=self.rich(index,action)
        self.reply=providers.response(value["coc"])
        coc_job=self.run_job("SEQ_COC",index)
        self.assertEqual(coc_job["status"],"SUCCEEDED",coc_job.get("error"))
        edit(self.service,self.ids[index],"sequence_coc",{"accepted_unchanged":True})
        approve(self.service,self.ids[index],"sequence_coc")
        self.reply=providers.response(value["constraints"])
        constraints_job=self.run_job("SEQ_CONSTRAINTS",index)
        self.assertEqual(constraints_job["status"],"SUCCEEDED",constraints_job.get("error"))
        return coc_job,constraints_job

    def test_wire_schema_closed_evidence_refs_low_reasoning_and_two_can_frames(self):
        self.connect()
        vehicle=providers.OpenAIProviderTests.vehicle_state(self)
        self.service.attach_vehicle_state(self.video,0,vehicle,"reviewer",uid())
        value=self.rich()
        self.reply=providers.response(value["coc"])
        job=self.run_job("SEQ_COC")
        self.assertEqual(job["status"],"SUCCEEDED",job.get("error"))
        wire=self.sent[0]
        self.assertEqual(wire["reasoning"],{"effort":"low"})
        sent=json.loads(wire["input"][0]["content"][0]["text"])
        self.assertEqual([f["timestamp_us"] for f in sent["frames"]],[5000000,6000000])
        self.assertEqual([f["frame_timestamp_us"] for f in sent["data"]["vehicle_state"]["frames"]],[5000000,6000000])
        refs=wire["text"]["format"]["schema"]["properties"]["evidence_refs"]["items"]["enum"]
        self.assertIn("CAN:5900000",refs)
        self.assertNotIn("CAN:100000",refs)
        self.assertEqual(sum(x["type"]=="input_image" for x in wire["input"][0]["content"]),2)
        self.assertEqual([f['role'] for f in sent['frames']],['PREVIOUS_COMPARISON','CURRENT'])
        scope=sent['data']['observation_scope']
        self.assertEqual(scope['current_frame_id'],self.store.moment(self.ids[6])['frame']['frame_id'])
        self.assertEqual(scope['previous_frame_id'],self.store.moment(self.ids[5])['frame']['frame_id'])
        content=wire['input'][0]['content']
        self.assertEqual([json.loads(content[i]['text'])['image_role'] for i in (1,3)],['PREVIOUS_COMPARISON','CURRENT'])
        self.assertEqual([content[i]['detail'] for i in (2,4)],['low','high'])
        self.assertEqual(self.store.moment(self.ids[6])['components']['sequence_coc']['payload']['observation_scope'],scope)

    def test_prior_only_entity_is_not_installed_as_current_coc(self):
        self.connect();value=self.rich()['coc'];self.reply=providers.response(value)
        self.assertEqual(self.run_job('SEQ_COC')['status'],'SUCCEEDED')
        before=deepcopy(self.store.moment(self.ids[6]))
        value['entities'][1]['evidence_refs']=[self.store.moment(self.ids[5])['frame']['frame_id']]
        self.reply=providers.response(value);job=self.run_job('SEQ_COC')
        self.assertEqual(job['status'],'FAILED')
        self.assertEqual(job['error']['code'],'PROVIDER_CURRENT_OBSERVATION')
        self.assertEqual(self.store.moment(self.ids[6]),before)
        self.assertEqual(self.store.objects('model_output')[-1]['code'],'PROVIDER_CURRENT_OBSERVATION')
        self.assertEqual(len(self.sent),2)  # No automatic retry.

    def test_prior_only_current_fact_is_rejected_but_unknown_can_be_retained(self):
        self.connect({**providers.config(),'max_calls':3});value=self.rich()
        self.reply=providers.response(value['coc']);self.assertEqual(self.run_job('SEQ_COC')['status'],'SUCCEEDED')
        edit(self.service,self.ids[6],'sequence_coc',{'accepted_unchanged':True});approve(self.service,self.ids[6],'sequence_coc')
        value['constraints']['facts'][0]['evidence_refs']=[self.store.moment(self.ids[5])['frame']['frame_id']]
        self.reply=providers.response(value['constraints']);job=self.run_job('SEQ_CONSTRAINTS')
        self.assertEqual(job['status'],'FAILED')
        self.assertEqual(job['error']['code'],'PROVIDER_CURRENT_OBSERVATION')
        self.assertNotIn('sequence_constraints',self.store.moment(self.ids[6])['components'])
        value['constraints']['facts'][0]['truth']='UNKNOWN'
        self.reply=providers.response(value['constraints']);job=self.run_job('SEQ_CONSTRAINTS')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        self.assertEqual(job['result']['parsed_candidate']['facts'][0]['truth'],'UNKNOWN')

    def test_current_can_supports_ego_state_but_not_signal_color(self):
        self.connect();self.service.attach_vehicle_state(self.video,0,providers.OpenAIProviderTests.vehicle_state(self),'reviewer',uid())
        value=self.rich()['coc'];value['entities'][0]['evidence_refs']=['CAN:5900000']
        value['relations']=[{'subject_ref':'ego','object_ref':None,'predicate':'STOPPED','truth':'FALSE','evidence_refs':['CAN:5900000']}]
        self.reply=providers.response(value);job=self.run_job('SEQ_COC')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        before=deepcopy(self.store.moment(self.ids[6]))
        value['entities'][1]['kind']='SIGNAL'
        value['relations']=[{'subject_ref':value['entities'][1]['entity_id'],'object_ref':None,'predicate':'SIGNAL_GREEN','truth':'TRUE','evidence_refs':['CAN:5900000']}]
        self.reply=providers.response(value);job=self.run_job('SEQ_COC')
        self.assertEqual(job['status'],'FAILED')
        self.assertEqual(job['error']['code'],'PROVIDER_CURRENT_OBSERVATION')
        self.assertEqual(self.store.moment(self.ids[6]),before)

    def test_original_contradiction_frozen_before_human_correction_and_catalog_changes(self):
        from apps.guardsynth_studio.sequence import catalog_edit, enqueue_stage
        _,job=self.generate_pair(0)
        # Constraints are unapproved, yet original quality must be captured.
        first=sequence_view(self.service,self.extraction)["quality"]
        self.assertEqual(first["first_pass"]["total"],1)
        self.assertEqual(first["first_pass"]["contradiction"],1)
        self.assertEqual(first["first_pass"]["pass"],0)
        frozen=deepcopy(self.store.objects("sequence_quality"))
        old=self.store.moment(self.ids[0])["components"]["sequence_coc"]["payload"]["original_candidate"]
        corrected=self.rich(0,"HOLD")["coc"]
        edit(self.service,self.ids[0],"sequence_coc",corrected);approve(self.service,self.ids[0],"sequence_coc")
        edit(self.service,self.ids[0],"sequence_constraints",{})
        edit(self.service,self.ids[0],"sequence_constraints",{"accepted_unchanged":True});approve(self.service,self.ids[0],"sequence_constraints")
        for kind in ["SEQ_EBLC","SEQ_VERIFY"]:
            queued=enqueue_stage(self.service,self.extraction,kind,"reviewer",uid());Worker(self.service).run_once()
            self.assertEqual(self.store.get(queued["job_id"],"job")["status"],"SUCCEEDED")
        quality=sequence_view(self.service,self.extraction)["quality"]
        self.assertEqual(quality["first_pass"]["contradiction"],1)
        self.assertEqual(quality["reviewed"]["pass"],1)
        self.assertEqual(self.store.moment(self.ids[0])["components"]["sequence_coc"]["payload"]["original_candidate"],old)
        catalog_edit(self.service,self.extraction,0,{"sources":[{"id":"policy","text":"test","locator":"test","reviewed":True,"expected_actions":[]}]} ,"reviewer",uid())
        self.assertEqual(sequence_view(self.service,self.extraction)["quality"]["first_pass"],first["first_pass"])
        self.assertEqual(self.store.objects("sequence_quality"),frozen)

    def test_empty_generated_pair_counts_as_review_required(self):
        self.connect(); value=self.rich(0,"HOLD")
        self.reply=providers.response(value["coc"]);self.assertEqual(self.run_job("SEQ_COC",0)["status"],"SUCCEEDED")
        edit(self.service,self.ids[0],"sequence_coc",{"accepted_unchanged":True});approve(self.service,self.ids[0],"sequence_coc")
        self.reply=providers.response({"new_definitions":[],"facts":[],"unresolved_previous_condition_refs":[],"unknowns":[]})
        job=self.run_job("SEQ_CONSTRAINTS",0);self.assertEqual(job["status"],"SUCCEEDED",job.get("error"))
        quality=sequence_view(self.service,self.extraction)["quality"]
        self.assertEqual(quality["first_pass"]["total"],1)
        self.assertEqual(quality["first_pass"]["review_required"],1)
        self.assertEqual(quality["first_pass"]["pass_rate"],0)


class GroundedContextStateTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich
    generate_pair=GroundedProviderTest.generate_pair

    def test_reviewed_target_metadata_survives_old_generation_context(self):
        from apps.guardsynth_studio.sequence import validation_context,input_diagnostics
        from guard_synth.studio_relations import errors
        from .test_grounded_sequence import fact
        self.generate_pair(0,'HOLD')
        edit(self.service,self.ids[0],'sequence_constraints',{'accepted_unchanged':True});approve(self.service,self.ids[0],'sequence_constraints')
        with self.store.transaction():
            old=self.store.moment(self.ids[0])
            for kind in ('sequence_coc','sequence_constraints'):old['components'][kind]['payload']['context_token']='old-generation-context'
            self.store.save(old,'historical reviewed context fixture')
        context,_=generation_context(self.service,self.store.moment(self.ids[2]))
        self.assertEqual(context['previous_definitions'],[])
        self.assertEqual(context['previous_states'],{})
        self.assertEqual({e['entity_id'] for e in context['inherited_entities']},{'ego','e1','e2'})
        current=self.rich(2,'HOLD')['coc'];current['entities']=current['entities'][:1]
        edit(self.service,self.ids[2],'sequence_coc',current);approve(self.service,self.ids[2],'sequence_coc')
        observed=fact('FALSE',predicate='PASSAGE_COMPLETE',subject='ego',target='e2')
        observed['evidence_refs']=[self.store.moment(self.ids[2])['frame']['frame_id']]
        constraints={'new_definitions':[],'facts':[observed],'unresolved_previous_condition_refs':[],'unknowns':[]}
        self.assertEqual(errors(constraints,validation_context(self.service,self.store.moment(self.ids[2]),'SEQ_CONSTRAINTS')),[])
        edit(self.service,self.ids[2],'sequence_constraints',constraints);approve(self.service,self.ids[2],'sequence_constraints')
        self.assertEqual(input_diagnostics(self.service,self.store.moment(self.ids[2]))['format_errors']['sequence_constraints'],[])

    def test_approved_definition_state_is_carried_without_old_imagery(self):
        self.generate_pair(0,"HOLD")
        edit(self.service,self.ids[0],"sequence_constraints",{"accepted_unchanged":True});approve(self.service,self.ids[0],"sequence_constraints")
        context,_=generation_context(self.service,self.store.moment(self.ids[1]))
        self.assertEqual(context["previous_states"],{"path_blocked":"ACTIVE"})
        self.assertEqual(len(context["previous_definitions"]),1)
        self.assertNotIn("frames",context)

    def test_generation_and_edit_context_keep_targets_after_unwritten_scene(self):
        from guard_synth.studio_grounded_sequence import grounded_schema
        from guard_synth.studio_relations import errors,generation_atom_schema
        from apps.guardsynth_studio.sequence import validation_context,input_diagnostics,_context
        from apps.guardsynth_studio.common import digest
        from .test_grounded_sequence import fact
        self.generate_pair(0,'HOLD')
        edit(self.service,self.ids[0],'sequence_constraints',{'accepted_unchanged':True});approve(self.service,self.ids[0],'sequence_constraints')
        context,token=generation_context(self.service,self.store.moment(self.ids[2]))
        self.assertEqual(context['previous_entities'],[])
        self.assertEqual({e['entity_id'] for e in context['inherited_entities']},{'ego','e1','e2'})
        self.assertTrue(all(set(e)=={'entity_id','kind','description'} for e in context['inherited_entities']))
        heads=[(identity,self.store.moment(identity)['revision']) for identity in self.ids[:2]]
        old_context=_context(context['catalog'],{d['condition_id']:d for d in context['previous_definitions']},context['previous_states'],None,context['human_assisted_context'])
        self.assertEqual(token,digest([old_context,heads]))
        value=self.rich(2,'HOLD')['coc'];value['entities']=value['entities'][:1]
        edit(self.service,self.ids[2],'sequence_coc',value);approve(self.service,self.ids[2],'sequence_coc')
        current=validation_context(self.service,self.store.moment(self.ids[2]),'SEQ_CONSTRAINTS')
        schema=grounded_schema('SEQ_CONSTRAINTS',current)
        self.assertIn('e2',schema['properties']['facts']['items']['properties']['atom']['properties']['object_ref']['enum'])
        atom_schema=generation_atom_schema(current)
        self.assertTrue(any(b['properties']['predicate']['enum']==['PASSAGE_COMPLETE'] and 'e2' in b['properties']['object_ref']['enum'] for b in atom_schema['anyOf']))
        f=fact(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')
        self.assertEqual(errors({'facts':[f]},current),[])
        self.assertEqual(input_diagnostics(self.service,self.store.moment(self.ids[2]))['inherited_entities'],context['inherited_entities'])

    def test_prior_change_before_queued_coc_sends_no_paid_request(self):
        self.connect()
        value=self.rich(0,"HOLD")["coc"]
        edit(self.service,self.ids[0],"sequence_coc",value);approve(self.service,self.ids[0],"sequence_coc")
        queued=self.service.enqueue(self.ids[1],0,"SEQ_COC","reviewer",uid())
        edit(self.service,self.ids[0],"sequence_coc",{"explanation":"앞 장면 교정"})
        Worker(self.service).run_once()
        job=self.store.get(queued["job_id"],"job")
        self.assertEqual(job["status"],"FAILED")
        self.assertEqual(job["error"]["code"],"PROVIDER_STALE")
        self.assertEqual(self.sent,[])
        self.assertEqual(self.service.capabilities()["call_budget"]["used"],0)

class GroundedBoundedContextTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich

    def test_full_64_condition_summary_fits_bounded_request_without_duplicates(self):
        from unittest.mock import patch
        from .test_grounded_sequence import definition
        self.connect()
        definitions=[definition(condition_id='condition_'+str(i),description='한국어 조건 설명 '*90) for i in range(64)]
        value=self.rich(6,'HOLD')
        context={'catalog':{'sources':[]},'known_conditions':definitions,'previous_definitions':definitions,
                 'previous_states':{d['condition_id']:'ACTIVE' for d in definitions},
                 'previous_entities':value['coc']['entities'],'previous_coc':value['coc'],'previous_moment_id':self.ids[5]}
        self.reply=providers.response(value['coc'])
        with patch('apps.guardsynth_studio.sequence.generation_context',return_value=(context,'fixed')):
            job=self.run_job('SEQ_COC')
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        data=json.loads(self.sent[0]['input'][0]['content'][0]['text'])['data']
        self.assertEqual(len(data['previous_definitions']),64)
        self.assertNotIn('known_conditions',data)
        self.assertNotIn('previous_coc',data)
        self.assertEqual(len(self.sent[0]['input'][0]['content']),5)

class GroundedExportTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich
    generate_pair=GroundedProviderTest.generate_pair

    def test_v2_snapshot_export_renders_structured_constraints(self):
        from apps.guardsynth_studio.sequence import enqueue_check,sequence_export
        self.generate_pair(0,'HOLD')
        edit(self.service,self.ids[0],'sequence_constraints',{'accepted_unchanged':True});approve(self.service,self.ids[0],'sequence_constraints')
        queued=enqueue_check(self.service,self.extraction,'reviewer',uid());Worker(self.service).run_once()
        self.assertEqual(self.store.get(queued['job_id'],'job')['status'],'SUCCEEDED')
        result=sequence_export(self.service,self.extraction)
        self.assertIn('보행자가 진입 경로를 점유함',result['samples'][0]['cnl'])
        self.assertFalse(result['training_eligible'])


class GroundedLargeExtractionTest(unittest.TestCase):
    def test_200_moment_contexts_keep_64_conditions_without_compiling_history(self):
        from unittest.mock import patch
        from .test_grounded_sequence import moment as grounded_moment,definition
        with TemporaryDirectory() as root:
            store,service,ids,extraction,_,_=fixture(root,200)
            try:
                for i in range(16):
                    m=store.moment(ids[i]);_,token=generation_context(service,m)
                    value=grounded_moment(i,definitions=[definition(condition_id="condition_"+str(j)) for j in range(i*4,(i+1)*4)])
                    frame=m["frame"]["frame_id"]
                    coc=value["coc"]
                    for entity in coc["entities"]:
                        entity["evidence_refs"]=[frame]
                        if i:
                            entity.update(identity_status="MATCHED_PREVIOUS",previous_entity_ref=entity["entity_id"])
                    coc["evidence_refs"]=[frame]
                    for action in coc["observed_actions"]:action["evidence_refs"]=[frame]
                    value["constraints"]["facts"][0]["evidence_refs"]=[frame]
                    with store.transaction():
                        store.install(m,"sequence_coc",{**coc,"context_token":token})
                        store.record_approval(m,"sequence_coc","APPROVE","fixture")
                        store.install(m,"sequence_constraints",{**value["constraints"],"context_token":token})
                        store.record_approval(m,"sequence_constraints","APPROVE","fixture")
                        store.save(m,"fixture")
                with patch("guard_synth.studio_sequence.compile_sequence",side_effect=AssertionError("Context summaries must not compile old scenes")):
                    for identity in ids:
                        context,_=generation_context(service,store.moment(identity))
                    self.assertEqual(len(context["previous_definitions"]),64)
                    self.assertEqual(len(context["previous_states"]),64)
                    self.assertEqual(context["previous_entities"],[])
                    self.assertEqual(context["previous_states"]["condition_0"],"ACTIVE")
            finally:
                store.close()

class GroundedQualityIsolationTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich
    generate_pair=GroundedProviderTest.generate_pair

    def test_quality_get_reads_frozen_records_without_solver_or_mutation(self):
        from unittest.mock import patch
        self.generate_pair(0)
        before=deepcopy(self.store.objects('sequence_quality'))
        with patch('apps.guardsynth_studio.sequence.capture_original_quality',side_effect=AssertionError('Quality GET must be read only')):
            quality=sequence_view(self.service,self.extraction)['quality']
        self.assertEqual(quality['first_pass']['contradiction'],1)
        self.assertEqual(self.store.objects('sequence_quality'),before)

    def test_original_quality_solver_child_runs_outside_database_transaction(self):
        from unittest.mock import patch
        from apps.guardsynth_studio import jobs
        called=[]; actual=jobs.child
        def checked_child(kind,request,timeout=None):
            if kind=='SEQ_QUALITY':
                self.assertFalse(self.store.db.in_transaction)
                self.assertEqual(len(request['moments']),1)
                called.append(kind)
            return actual(kind,request,timeout)
        with patch('apps.guardsynth_studio.jobs.child',side_effect=checked_child):
            self.generate_pair(0)
        self.assertEqual(len(called),1)

class GroundedPriorCorrectionQualityTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich
    generate_pair=GroundedProviderTest.generate_pair

    def test_prior_fact_correction_marks_generated_pair_as_human_assisted(self):
        self.generate_pair(0,'HOLD')
        original=deepcopy(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'])
        corrected=deepcopy(original);corrected['facts'][0]['truth']='FALSE'
        edit(self.service,self.ids[0],'sequence_constraints',corrected);approve(self.service,self.ids[0],'sequence_constraints')
        value=self.rich(1,'HOLD')
        for e in value['coc']['entities']:
            e.update(identity_status='MATCHED_PREVIOUS',previous_entity_ref=e['entity_id'])
        # Grant two more synthetic calls; this transport is local and never contacts a model.
        self.service.provider.config['max_calls']=4
        self.reply=providers.response(value['coc'])
        self.assertEqual(self.run_job('SEQ_COC',1)['status'],'SUCCEEDED')
        edit(self.service,self.ids[1],'sequence_coc',{'accepted_unchanged':True});approve(self.service,self.ids[1],'sequence_coc')
        value['constraints']['new_definitions']=[]
        self.reply=providers.response(value['constraints'])
        job=self.run_job('SEQ_CONSTRAINTS',1);self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        quality=sequence_view(self.service,self.extraction)['quality']
        item=quality['items'][1]
        self.assertTrue(item['human_assisted_pair'])
        self.assertEqual(item['first_pass']['logical_status'],'PASS')
        self.assertEqual(item['first_pass']['status'],'REVIEW_REQUIRED')
        self.assertEqual(quality['first_pass']['pass'],1)

class GroundedOutputLimitTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich

    def test_valid_structured_output_over_legacy_dto_cap_is_preserved(self):
        self.connect();value=self.rich(0,'HOLD')['coc']
        value['observations']='관찰된 장면과 확인 한계. '*700
        self.reply=providers.response(value)
        job=self.run_job('SEQ_COC',0)
        self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        saved=self.store.moment(self.ids[0])['components']['sequence_coc']['payload']
        self.assertEqual(saved['original_candidate'],value)
        self.assertEqual(json.loads(saved['raw_output']),value)

class GroundedCocLineageQualityTest(unittest.TestCase):
    setUp=providers.OpenAIProviderTests.setUp
    connect=providers.OpenAIProviderTests.connect
    run_job=providers.OpenAIProviderTests.run_job
    rich=GroundedProviderTest.rich
    generate_pair=GroundedProviderTest.generate_pair

    def test_prior_coc_correction_remains_assisted_through_third_generation(self):
        self.generate_pair(0,'HOLD')
        self.service.provider.config['max_calls']=6
        edit(self.service,self.ids[0],'sequence_coc',{'explanation':'검토자의 설명 교정'})
        approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',{'accepted_unchanged':True})
        approve(self.service,self.ids[0],'sequence_constraints')
        for i in [1,2]:
            value=self.rich(i,'HOLD')
            for e in value['coc']['entities']:
                e.update(identity_status='MATCHED_PREVIOUS',previous_entity_ref=e['entity_id'])
            self.reply=providers.response(value['coc'])
            coc_job=self.run_job('SEQ_COC',i)
            self.assertEqual(coc_job['status'],'SUCCEEDED',coc_job.get('error'))
            edit(self.service,self.ids[i],'sequence_coc',{'accepted_unchanged':True})
            approve(self.service,self.ids[i],'sequence_coc')
            value['constraints']['new_definitions']=[]
            self.reply=providers.response(value['constraints'])
            constraints_job=self.run_job('SEQ_CONSTRAINTS',i)
            self.assertEqual(constraints_job['status'],'SUCCEEDED',constraints_job.get('error'))
            edit(self.service,self.ids[i],'sequence_constraints',{'accepted_unchanged':True})
            approve(self.service,self.ids[i],'sequence_constraints')
        quality=sequence_view(self.service,self.extraction)['quality']
        self.assertTrue(quality['items'][1]['human_assisted_pair'])
        self.assertTrue(quality['items'][2]['human_assisted_pair'])
        self.assertEqual(quality['items'][2]['first_pass']['logical_status'],'PASS')
        self.assertEqual(quality['items'][2]['first_pass']['status'],'REVIEW_REQUIRED')
        self.assertEqual(quality['first_pass']['pass'],1)
