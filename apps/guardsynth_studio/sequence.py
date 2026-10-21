"""Additive, revision-bound recorded CoC workflow; no implicit model calls."""
from copy import deepcopy
import subprocess

from guard_synth.studio_sequence import candidate_schema, validate_candidate, render_constraints, ACTIONS, tool_signature
from .common import StudioError, digest, now

KINDS = {"SEQ_COC": "sequence_coc", "SEQ_CONSTRAINTS": "sequence_constraints"}


def catalog(service, identity):
    service.store.get(identity, "extraction")
    try:
        return service.store.get("sequence-catalog-"+identity,"sequence_catalog")
    except StudioError as exc:
        if exc.status!=404: raise
        return {"revision":0,"sources":[]}


def catalog_edit(service, identity, revision, data, actor, key):
    def operation():
        current=catalog(service,identity)
        if current["revision"]!=revision: raise StudioError("STALE","규칙 목록이 변경되었습니다. 다시 읽어 비교하세요.",409)
        if set(data)!={"sources"} or not isinstance(data["sources"],list) or len(data["sources"])>64:
            raise StudioError("CATALOG","규칙 sources 목록은 최대 64개입니다.")
        ids=set()
        for s in data["sources"]:
            if (not isinstance(s,dict) or set(s)!={"id","text","locator","reviewed","expected_actions"}
                or any(not isinstance(s[k],str) or not s[k].strip() for k in ("id","text","locator"))
                or s["id"] in ids or type(s["reviewed"]) is not bool
                or not isinstance(s["expected_actions"],list) or not set(s["expected_actions"]).issubset(ACTIONS)):
                raise StudioError("CATALOG","규칙 ID·원문·위치·검토 확인·관련 행동을 입력하세요.")
            ids.add(s["id"])
        value={"revision":revision+1,"sources":deepcopy(data["sources"]),"actor":actor,"updated":now()}
        service.store.put("sequence_catalog",value,"sequence-catalog-"+identity)
        return value
    return service.store.mutate(actor,key,["sequence_catalog",identity,revision,data],operation)


def sequence_frames(service, moment):
    return service.causal_frames(moment)[-2:]


def sequence_vehicle_state(service, moment):
    state = service.causal_vehicle_state(moment)
    if state is not None:
        state = deepcopy(state)
        times = {f["timestamp_us"] for f in sequence_frames(service, moment)}
        state["frames"] = [f for f in state["frames"] if f["frame_timestamp_us"] in times]
    return state



def current_evidence(service, moment, vehicle=None):
    refs = [moment["frame"]["frame_id"]]
    if vehicle:
        refs.extend("CAN:"+str(f["sample"]["timestamp_us"]) for f in vehicle["frames"] if f["frame_timestamp_us"] == moment["t0_us"] and f.get("sample"))
    return refs

def observation_scope(moment, frames, vehicle=None):
    previous=frames[-2] if len(frames)>1 else None
    current=frames[-1]
    refs=[current['frame_id']]
    if vehicle:
        refs.extend('CAN:'+str(f['sample']['timestamp_us']) for f in vehicle['frames'] if f['frame_timestamp_us']==moment['t0_us'] and f.get('sample'))
    return {'current_frame_id':current['frame_id'], 'current_timestamp_us':current['timestamp_us'],
            'previous_frame_id':previous['frame_id'] if previous else None,
            'previous_timestamp_us':previous['timestamp_us'] if previous else None, 'current_evidence_ids':refs}

def generation_context(service, moment):
    rows = list(service.store.db.execute("SELECT id, head, ordinal FROM moments WHERE extraction=? ORDER BY ordinal LIMIT 200",
                                        (moment["extraction_id"],)))
    cat = catalog(service, moment["extraction_id"])
    key = digest([cat, [(r["id"],r["head"]) for r in rows]])
    cache = getattr(service, "_sequence_context_cache", {})
    cached = cache.get(moment["extraction_id"])
    if cached and cached[0] == key:
        return deepcopy(cached[1][moment["id"]])
    definitions, legacy_definitions, states, heads, previous_coc = {}, {}, {}, [], None
    target_entities, target_conditions = {}, set()
    prior_assisted=False
    contexts, legacy_tokens = {}, {}
    for row in rows:
        m = service.store.moment(row["id"])
        context = _context(cat, definitions, states, previous_coc, prior_assisted)
        valid_token = digest([context, heads])
        # Derived metadata is already bound by the preceding revision heads.
        # Adding it must not invalidate otherwise unchanged saved candidates.
        context["inherited_entities"] = deepcopy(list(target_entities.values()))
        contexts[m["id"]] = (deepcopy(context), valid_token)
        legacy_context = {"catalog": cat, "known_conditions": list(legacy_definitions.values())[:64]}
        legacy_token = digest([legacy_context, heads])
        legacy_tokens[m["id"]] = legacy_token
        c = m["components"].get("sequence_constraints")
        compatible = c and c["payload"].get("context_token") in (valid_token, legacy_token) and not constraint_binding_issue(service,m)
        if c and service.store.approved(m, "sequence_constraints") and compatible:
            data = c["payload"]
            prior_assisted = (prior_assisted or candidate(data,"sequence_constraints") != data.get("original_candidate")
                              or data.get("original_sequence_context",{}).get("human_assisted_context",False))
            for condition in data.get("new_definitions", data.get("constraints", [])):
                definition = {k: v for k, v in condition.items() if k not in ("truth", "scope_state", "evidence_refs", "evidence_note")}
                if "new_definitions" in data and (len(definitions) < 64 or condition["condition_id"] in definitions):
                    definitions.setdefault(condition["condition_id"], definition)
                if "constraints" in data and (len(legacy_definitions)<64 or condition["condition_id"] in legacy_definitions):
                    legacy_definitions.setdefault(condition["condition_id"], definition)
            if "new_definitions" in data:
                from guard_synth.studio_grounded_sequence import grounded_state_summary
                states = grounded_state_summary(list(definitions.values()), states, candidate(data,"sequence_constraints"),
                                                current_evidence(service,m,data.get("vehicle_state_input")),
                                                candidate(m["components"].get("sequence_coc",{}).get("payload",{}),"sequence_coc"),
                                                context["previous_entities"],context["inherited_entities"])
        coc = m["components"].get("sequence_coc")
        # Reviewed target definitions remain usable for editing inherited facts
        # even when an old generation token no longer matches. This retains no
        # observation truth and does not promote that context's rules or states.
        if c and coc and service.store.approved(m,"sequence_constraints") and service.store.approved(m,"sequence_coc") and not constraint_binding_issue(service,m):
            from guard_synth.studio_grounded_sequence import definition_entities
            entities=context["inherited_entities"]+context["previous_entities"]+coc["payload"].get("entities",[])
            for definition in c["payload"].get("new_definitions",[]):
                cid=definition["condition_id"]
                if cid in target_conditions or len(target_conditions)>=64:continue
                target_entities.update(definition_entities(definition,entities));target_conditions.add(cid)
        coc_valid = coc and service.store.approved(m, "sequence_coc") and ("context_token" not in coc["payload"] or coc["payload"]["context_token"] == valid_token)
        if coc_valid:
            payload=coc["payload"]
            prior_assisted = (prior_assisted or candidate(payload,"sequence_coc") != payload.get("original_candidate")
                              or payload.get("original_sequence_context",{}).get("human_assisted_context",False))
        previous_coc = (m["id"], candidate(coc["payload"], "sequence_coc")) if coc_valid else None
        heads.append((m["id"], m["revision"]))
    cache[moment["extraction_id"]] = (key, contexts, legacy_tokens)
    service._sequence_context_cache = cache
    return deepcopy(contexts[moment["id"]])


def context_current(service, moment, kind):
    component = moment["components"].get(kind)
    if not component or "context_token" not in component["payload"]: return True
    expected = generation_context(service, moment)[1]
    token = component["payload"]["context_token"]
    if token == expected: return True
    if kind == "sequence_constraints" and "new_definitions" not in component["payload"]:
        return token == service._sequence_context_cache[moment["extraction_id"]][2][moment["id"]]
    return False


def _context(cat, definitions, states, previous_coc, prior_assisted=False):
    return {"catalog": cat, "known_conditions": list(definitions.values())[:64],
            "previous_definitions": list(definitions.values())[:64], "previous_states": deepcopy(states),
            "human_assisted_context": prior_assisted,
            "previous_moment_id": previous_coc[0] if previous_coc else None,
            "previous_coc": deepcopy(previous_coc[1]) if previous_coc else None,
            "previous_entities": deepcopy(previous_coc[1].get("entities", [])) if previous_coc else []}


def candidate(data, kind):
    task = next(k for k,v in KINDS.items() if v == kind)
    schema = candidate_schema(task)
    if (kind == "sequence_coc" and "entities" not in data) or (kind == "sequence_constraints" and "new_definitions" not in data):
        from guard_synth.studio_sequence import legacy_schema
        schema = legacy_schema(task)
    optional={"reason_bindings","action_observation_complete"}
    return {k: deepcopy(data.get(k)) for k in schema["properties"] if k not in optional or k in data}


def validation_context(service, moment, task):
    context = generation_context(service, moment)[0]
    frames = sequence_frames(service, moment)
    evidence = {f["frame_id"] for f in frames}
    state = sequence_vehicle_state(service, moment)
    if state:
        evidence.update("CAN:"+str(f["sample"]["timestamp_us"]) for f in state["frames"] if f.get("sample"))
    context.update(frame_ids=sorted(evidence), evidence_ids=sorted(evidence),
                   source_ids=[s["id"] for s in context["catalog"]["sources"]])
    if task == "SEQ_CONSTRAINTS":
        context["coc"] = candidate(moment["components"].get("sequence_coc",{}).get("payload",{}), "sequence_coc")
        context["current_entities"] = context["coc"].get("entities", [])
    return context


def entity_binding(entities):
    return {e["entity_id"]:{"kind":e["kind"],"description":e["description"]} for e in entities}


def constraint_baseline(service, moment):
    component=moment["components"].get("sequence_constraints",{})
    payload=component.get("payload",{})
    if "new_definitions" not in payload: return None
    baseline=payload.get("entity_binding")
    if baseline is None and payload.get("coc_used") is not None:
        baseline=entity_binding(payload["coc_used"].get("entities",[]))
    if baseline is None:
        # Historical human drafts have their original CoC in revision history.
        identity=component.get("dependencies",{}).get("sequence_coc")
        if identity:
            for row in service.store.db.execute("SELECT data FROM revisions WHERE moment=? ORDER BY revision DESC",(moment["id"],)):
                import json
                previous=json.loads(row["data"])["components"].get("sequence_coc",{})
                if previous.get("id")==identity:
                    baseline=entity_binding(previous["payload"].get("entities",[]));break
    return baseline


def constraint_generation_issue(service, moment):
    component=moment["components"].get("sequence_constraints")
    coc=moment["components"].get("sequence_coc",{})
    current=coc.get("payload",{}).get("generation_job_id")
    if not component or not current: return None
    data=component["payload"]
    baseline=data.get("original_coc_generation_id",data.get("coc_generation_id"))
    if baseline is None:
        identity=component.get("dependencies",{}).get("sequence_coc")
        for row in service.store.db.execute("SELECT data FROM revisions WHERE moment=? ORDER BY revision DESC",(moment["id"],)):
            import json
            old=json.loads(row["data"])["components"].get("sequence_coc",{})
            if old.get("id")==identity:
                baseline=old.get("payload",{}).get("generation_job_id",old.get("id"));break
    if baseline is not None and baseline!=current:
        return "CoC가 새로 생성되어 이전 제약을 사용할 수 없습니다. 현재 CoC를 검토한 뒤 제약 → EBLC → 검증 → CNL을 새로 실행하세요. 이전 제약은 이력으로만 보존됩니다."
    return None


def constraint_binding_issue(service, moment):
    generation=constraint_generation_issue(service,moment)
    if generation: return generation
    payload=moment["components"].get("sequence_constraints",{}).get("payload",{})
    baseline=constraint_baseline(service,moment)
    if baseline is None: return None
    current=entity_binding(moment["components"].get("sequence_coc",{}).get("payload",{}).get("entities",[]))
    refs=set()
    def collect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.endswith("_ref") and item: refs.add(item)
                elif key=="condition_target_refs": refs.update(item)
                else: collect(item)
        elif isinstance(value,list):
            for item in value: collect(item)
    collect(candidate(payload,"sequence_constraints"))
    if any(current.get(ref)!=baseline.get(ref) for ref in refs if ref in current or ref in baseline):
        return "CoC의 대상 목록이 제약 생성 당시와 달라 이전 연결을 재사용할 수 없습니다. 현재 CoC를 검토한 뒤 제약을 다시 생성하세요. 확인 상태만 바꾸거나 다시 승인해도 해결되지 않습니다."
    return None


def input_diagnostics(service, moment):
    from guard_synth.studio_relations import errors
    inherited=generation_context(service,moment)[0].get("inherited_entities",[])
    context={"coc":moment["components"].get("sequence_coc",{}).get("payload",{}),"inherited_entities":inherited}
    return {"inherited_entities":inherited,"constraint_binding":constraint_binding_issue(service,moment),
            "constraint_generation":constraint_generation_issue(service,moment),
            "format_errors":{kind:errors(candidate(component["payload"],kind),{**context,"previous_entities":component["payload"].get("original_sequence_context",{}).get("previous_entities",[])})
                             for kind,component in moment["components"].items() if kind in KINDS.values()}}


def validate_edit(service, moment, kind, incoming):
    if kind=="sequence_constraints":
        issue=constraint_generation_issue(service,moment)
        if issue: raise StudioError("CONSTRAINT_GENERATION",issue,409)
    task=next(k for k,v in KINDS.items() if v==kind)
    old=moment["components"].get(kind,{}).get("payload",{})
    fields=set(candidate({**old,**incoming},kind))
    if set(incoming)-fields-{"accepted_unchanged"}: raise StudioError("PROVENANCE","모델 원문·생성 기록은 변경할 수 없습니다.")
    data={**deepcopy(old),**incoming}
    current=candidate(data,kind)
    context=validation_context(service,moment,task)
    modern="entities" in current or "new_definitions" in current
    frames=set(context["evidence_ids"]) if modern else {f["frame_id"] for f in service.causal_frames(moment)}
    source_ids={s["id"] for s in catalog(service,moment["extraction_id"])["sources"]}
    validate_candidate(task,current,frames,source_ids,context)
    original=data.get("original_candidate")
    changed=original is not None and current!=original
    if incoming.get("accepted_unchanged") is True and (original is None or changed):
        raise StudioError("SEQUENCE_REVIEW","수정 없는 모델 원문만 그대로 수용할 수 있습니다.")
    if "accepted_unchanged" in incoming and type(incoming["accepted_unchanged"]) is not bool:
        raise StudioError("SEQUENCE_REVIEW","수용 확인은 체크 값이어야 합니다.")
    if changed: data["accepted_unchanged"]=False
    if kind=="sequence_constraints" and modern and "entity_binding" not in data:
        data["entity_binding"]=constraint_baseline(service,moment) or entity_binding(context.get("coc",{}).get("entities",[]))
    if kind=="sequence_constraints" and "coc_generation_id" not in data:
        data["coc_generation_id"]=moment["components"].get("sequence_coc",{}).get("payload",{}).get("generation_job_id")
    data.setdefault("origin","HUMAN")
    data["context_token"]=generation_context(service,moment)[1]
    return data


def require_entity_coc(moment):
    entities=moment["components"].get("sequence_coc",{}).get("payload",{}).get("entities",[])
    if not any(e.get("entity_id")=="ego" and e.get("kind")=="EGO" for e in entities):
        raise StudioError("SEQUENCE_FORMAT","CoC에 장면 대상 정보가 없습니다. 1단계에서 CoC를 다시 생성·검토한 뒤 제약을 생성하세요. 모델 호출은 실행되지 않았습니다.")


def validate_approval(service, moment, kind):
    data=moment["components"][kind]["payload"]
    if moment["components"][kind]["stale"]:
        raise StudioError("STALE","입력이 바뀌었습니다. 최신 입력으로 수정하거나 생성하세요.",409)
    if kind=="sequence_constraints":
        service.require_approvals(moment,("sequence_coc",))
        if "new_definitions" in data: require_entity_coc(moment)
        message=constraint_binding_issue(service,moment)
        if message: raise StudioError("CONSTRAINT_ENTITY_BINDING",message,409)
    task="SEQ_COC" if kind=="sequence_coc" else "SEQ_CONSTRAINTS"
    current=candidate(data,kind)
    context=validation_context(service,moment,task)
    frames=set(context["evidence_ids"]) if "entities" in current or "new_definitions" in current else {f["frame_id"] for f in service.causal_frames(moment)}
    validate_candidate(task,current,frames,
                       {s["id"] for s in catalog(service,moment["extraction_id"])["sources"]},
                       context)
    if "entities" in current or "new_definitions" in current:
        from guard_synth.studio_relations import errors
        issues=errors(current,context)
        if issues: raise StudioError("RELATION_FORMAT",issues[0]["message"])
    if kind=="sequence_coc" and not data["explanation"].strip(): raise StudioError("SEQUENCE_REVIEW","CoC 설명을 입력하세요.")
    if data.get("original_candidate")==candidate(data,kind) and data.get("accepted_unchanged") is not True:
        raise StudioError("SEQUENCE_REVIEW","수정이 없으면 모델 제안 그대로 수용을 확인하세요.")


def enqueue_sequence(service, identity, revision, kind, actor, key):
    from .provider import PROMPT_VERSIONS, OpenAIProvider
    if service.provider.mode=="DISABLED": raise StudioError("PROVIDER_NOT_CONFIGURED","모델 설정이 필요합니다.",503)
    def operation():
        m=service.store.require_head(identity,revision)
        if kind=="SEQ_CONSTRAINTS":
            service.require_approvals(m,("sequence_coc",))
            if isinstance(service.provider,OpenAIProvider): require_entity_coc(m)
        context,token=generation_context(service,m)
        inputs={"moment":m,"frames":sequence_frames(service,m),"t0_us":m["t0_us"],
                "prompt_version":PROMPT_VERSIONS[kind]}
        vehicle=sequence_vehicle_state(service,m)
        if vehicle is not None: inputs["vehicle_state"]=vehicle
        inputs['observation_scope']=observation_scope(m,inputs['frames'],vehicle)
        inputs.update(sequence_context=context,context_token=token)
        if kind=="SEQ_CONSTRAINTS":
            coc=m["components"]["sequence_coc"]
            inputs["original_coc"]=deepcopy(coc["payload"].get("original_candidate"))
            inputs["coc_used"]=candidate(coc["payload"],"sequence_coc")
            inputs["original_coc_generation_id"]=coc["payload"].get("generation_job_id",coc["id"])
            inputs["original_prior"]=original_prior(service,m)
        return {"job_id":service.new_job(kind,inputs,actor,m)}
    return service.store.mutate(actor,key,["sequence_job",identity,revision,kind],operation)


def snapshot(service, identity):
    cat=catalog(service,identity)
    extraction=service.store.get(identity,"extraction")
    video=service.store.get(extraction["video_id"],"video")
    rows=service.store.db.execute("SELECT id FROM moments WHERE extraction=? ORDER BY ordinal",(identity,))
    moments=[service.store.moment(r[0]) for r in rows]
    if not 1<=len(moments)<=200: raise StudioError("SEQUENCE_SIZE","전체 추출의 1–200개 시점을 검사할 수 있습니다.")
    return {"extraction_id":identity,"catalog":cat,"video_revision":video["revision"],"permission":video["permission"],
            "frame_manifest_digest":digest(extraction["frames"]),"tool_signature":tool_signature(),"moments":moments}


def check_inputs(service, snap):
    moments=[]
    prior=None
    extraction=service.store.get(snap["extraction_id"],"extraction")
    threshold=2*extraction.get("interval_s",1)*1000000
    empty={"observations":"","observed_actions":[],"explanation":"","unknowns":"미작성","evidence_refs":[]}
    for stored in snap["moments"]:
        m=deepcopy(stored)
        service.refresh_tool_versions(m)
        coc=m["components"].get("sequence_coc",{}).get("payload",{})
        constraints=m["components"].get("sequence_constraints",{}).get("payload",{})
        reviewed=all(service.store.approved(m,k) for k in KINDS.values())
        if reviewed and ("entities" in coc or "new_definitions" in constraints):
            diagnostics=input_diagnostics(service,m)
            if diagnostics["constraint_binding"]:
                raise StudioError("CONSTRAINT_ENTITY_BINDING",f"시점 {m['ordinal']+1}: "+diagnostics["constraint_binding"],409)
            for items in diagnostics["format_errors"].values():
                if items: raise StudioError("RELATION_FORMAT",f"시점 {m['ordinal']+1}: "+items[0]["message"])
        # Legacy candidates were generated from up to seven causal frames.
        # Keep those valid IDs; modern candidates retain the two-frame window.
        modern="entities" in coc or "new_definitions" in constraints
        frames=sequence_frames(service,m) if modern else service.causal_frames(m)
        frame_ids=[f["frame_id"] for f in frames]
        vehicle=sequence_vehicle_state(service,m) if modern else service.causal_vehicle_state(m)
        if vehicle:
            frame_ids.extend("CAN:"+str(f["sample"]["timestamp_us"]) for f in vehicle["frames"] if f.get("sample"))
        moments.append({"id":m["id"],"ordinal":m["ordinal"],"t0_us":m["t0_us"],"reviewed":reviewed,
                        "frame_ids":frame_ids,"current_evidence_refs":current_evidence(service,m,vehicle),
                        "vehicle_state":vehicle,
                        "coc":candidate(coc,"sequence_coc") if coc else empty,
                        "constraints":candidate(constraints,"sequence_constraints") if constraints else {"constraints":[]},
                        "observation_gap":prior is not None and m["t0_us"]-prior>threshold})
        prior=m["t0_us"]
    return moments


def enqueue_check(service, identity, actor, key):
    def operation():
        snap=snapshot(service,identity)
        if not snap["permission"]: raise StudioError("PERMISSION_REVOKED","영상 사용 권한을 확인하세요.",409)
        inputs={"snapshot":snap,"snapshot_digest":digest(snap),"moments":check_inputs(service,snap),"catalog":snap["catalog"]}
        return {"job_id":service.new_job("SEQ_CHECK",inputs,actor)}
    return service.store.mutate(actor,key,["sequence_check",identity],operation)


def latest(service, identity):
    jobs=service.store.job_ids(kind="SEQ_CHECK", extraction=identity, newest_first=True, limit=1)
    return service.store.job(jobs[0]) if jobs else None


def sequence_view(service, identity):
    cat=catalog(service,identity);job=latest(service,identity)
    stale=job is not None and (job["inputs"]["snapshot_digest"]!=digest(snapshot(service,identity)) or job["status"]=="STALE_RESULT")
    stages={};snap=snapshot(service,identity)
    for kind,label in STAGES.items():
        item=latest_stage(service,identity,kind)
        stages[label]={"job_id":item["id"] if item else None,"job_status":item["status"] if item else None,
                       "input_revisions":{m['id']:m['revision'] for m in item['inputs']['snapshot']['moments']} if item else {},
                       "stale":item is not None and not stage_current(service,item),"result":item.get("result") if item else None}
        if kind=="SEQ_VERIFY" and item and item.get("result") and item["inputs"].get("compiled"):
            from .review_summary import summarize
            stages[label]["review_summary"]=summarize(item["inputs"]["compiled"],item["result"],item["inputs"]["snapshot"])
    verification=latest_stage(service,identity,'SEQ_VERIFY')
    baseline=verification
    if verification and not verification.get('result'):
        previous=service.store.job_ids(kind='SEQ_VERIFY', extraction=identity, statuses=('SUCCEEDED',), newest_first=True, limit=1)
        baseline=service.store.job(previous[0]) if previous else None
    if verification and not stages['verification']['stale']:
        previous=(service.store.job(i) for i in service.store.job_ids(kind='SEQ_VERIFY', extraction=identity, statuses=('SUCCEEDED',), newest_first=True)
                  if i!=verification['id'])
        baseline=next((j for j in previous if any(
            candidate(old.get('components',{}).get(k,{}).get('payload',{}),k)!=candidate(new.get('components',{}).get(k,{}).get('payload',{}),k)
            for old,new in zip(j['inputs']['snapshot']['moments'],snap['moments']) for k in KINDS.values())),None)
    if baseline and baseline.get('result'):
        from .review_summary import correction_review
        stages['verification']['correction_review']=correction_review(baseline,verification,snap,stages['verification'].get('review_summary'),stages['verification']['stale'])
    from guard_synth.studio_relations import grammar
    return {"relation_grammar":grammar(),"input_diagnostics":{m["id"]:input_diagnostics(service,m) for m in snap["moments"]},
            "catalog":cat,"stale":stale,"job_id":job["id"] if job else None,
            "job_status":job["status"] if job else None,"result":job.get("result") if job else None,"stages":stages,"quality":quality(service,identity)}


def sequence_export(service, identity):
    view=sequence_view(service,identity);job=latest(service,identity)
    if not job or job["status"]!="SUCCEEDED" or view["stale"]:
        raise StudioError("SEQUENCE_SNAPSHOT","최신 입력으로 연속 검사를 실행한 뒤 내려받으세요.",409)
    samples=[]
    for m in job["inputs"]["snapshot"]["moments"]:
        c=m["components"].get("sequence_coc",{}).get("payload",{})
        bundle=m["components"].get("sequence_constraints",{}).get("payload",{})
        if "new_definitions" in bundle:
            from guard_synth.studio_grounded_sequence import render_grounded_constraints
            checked=next((r for r in job["result"].get("scenes",[]) if r.get("moment_id")==m["id"]),{})
            labels={e['entity_id']:e['description'] for e in c.get('entities',[])}
            definitions=checked.get("constraints",bundle["new_definitions"])
            cnl=render_grounded_constraints(definitions,labels)
            cnl_details=render_grounded_constraints(definitions,labels,detailed=True)
        else:
            cnl=render_constraints(bundle.get("constraints",[]))
            cnl_details=cnl
        samples.append({"pair_id":m["id"],"t0_us":m["t0_us"],"original_coc":bundle.get("original_coc",c.get("original_candidate")),
                        "reviewed_coc":candidate(c,"sequence_coc") if c else None,
                        "constraints":bundle,"cnl":cnl,"cnl_details":cnl_details,"combined":c.get("explanation","")+"\n"+cnl,
                        "training_eligible":False,"review_revision":m["revision"]})
    return {"project_id":"guardsynth-coc","subproject_id":"guardsynth-studio-sequential-coc","purpose":"DRAFT",
            "training_eligible":False,"snapshot_digest":job["inputs"]["snapshot_digest"],
            "catalog":job["inputs"]["catalog"],"samples":samples,"verification":job["result"]}


STAGES={"SEQ_EBLC":"eblc","SEQ_VERIFY":"verification","SEQ_CNL":"cnl"}


def latest_stage(service,identity,kind):
    jobs=service.store.job_ids(kind=kind, extraction=identity, newest_first=True, limit=1)
    return service.store.job(jobs[0]) if jobs else None


def stage_current(service,job):
    if not job or job["status"]!="SUCCEEDED": return False
    identity=job["inputs"]["snapshot"]["extraction_id"]
    if job["inputs"]["snapshot_digest"]!=digest(snapshot(service,identity)): return False
    if latest_stage(service,identity,job["kind"])["id"]!=job["id"]: return False
    parent_id=job["inputs"].get("parent_job_id")
    return not parent_id or stage_current(service,service.store.get(parent_id,"job"))


def enqueue_stage(service,identity,kind,actor,key):
    if kind not in STAGES: raise StudioError("JOB","지원하지 않는 생성 단계입니다.")
    def operation():
        snap=snapshot(service,identity)
        if not snap["permission"]: raise StudioError("PERMISSION_REVOKED","영상 사용 권한을 확인하세요.",409)
        inputs={"snapshot":snap,"snapshot_digest":digest(snap)}
        if kind=="SEQ_EBLC":
            moments=check_inputs(service,snap)
            if not any(m["reviewed"] for m in moments):
                raise StudioError("APPROVAL_REQUIRED","CoC와 제약을 먼저 검토 확인하세요.",409)
            inputs.update(moments=moments,catalog=snap["catalog"])
        else:
            parent_kind="SEQ_EBLC" if kind=="SEQ_VERIFY" else "SEQ_VERIFY"
            parent=latest_stage(service,identity,parent_kind)
            if not stage_current(service,parent):
                raise StudioError("STAGE_REQUIRED","앞 단계를 최신 입력으로 먼저 실행하세요.",409)
            inputs.update(parent_job_id=parent["id"])
            if kind=="SEQ_VERIFY": inputs["compiled"]=deepcopy(parent["result"])
            else:
                build=service.store.get(parent["inputs"]["parent_job_id"],"job")
                inputs.update(compiled=deepcopy(build["result"]),verification=deepcopy(parent["result"]))
        return {"job_id":service.new_job(kind,inputs,actor)}
    return service.store.mutate(actor,key,["sequence_stage",identity,kind],operation)



def original_prior(service, moment):
    signature=tool_signature()
    records={r["pair_id"]:r for r in service.store.objects("sequence_quality")}
    rows=service.store.db.execute("SELECT id FROM moments WHERE extraction=? AND ordinal<? ORDER BY ordinal DESC LIMIT 200",
                                  (moment["extraction_id"],moment["ordinal"]))
    for row in rows:
        earlier=service.store.moment(row[0])
        bundle=earlier["components"].get("sequence_constraints",{}).get("payload",{})
        pair=digest([bundle.get("original_coc_generation_id"),bundle.get("generation_job_id"),signature])
        record=records.get(pair)
        if record and record.get("continuation_summary"):
            return {"original_input":deepcopy(record["original_input"]),
                    "continuation_summary":deepcopy(record["continuation_summary"]),
                    "generation_ids":record["generation_ids"],"pair_id":record["pair_id"]}
    return None

def capture_original_quality(service, moment):
    """Freeze the first verifier result for this exact unedited generation pair."""
    from .jobs import child
    bundle = moment["components"].get("sequence_constraints", {}).get("payload", {})
    original = bundle.get("original_candidate")
    coc = bundle.get("original_coc")
    if not original or not bundle.get("generation_job_id"):
        return None
    pair = [bundle.get("original_coc_generation_id"), bundle.get("generation_job_id"), tool_signature()]
    identity = "sequence-quality-" + digest(pair)
    try:
        return service.store.get(identity, "sequence_quality")
    except StudioError as exc:
        if exc.status != 404: raise
    context = bundle.get("original_sequence_context", {})
    previous = bundle.get("original_prior")
    initial = previous.get("continuation_summary") if previous else None
    frames = bundle.get("input_manifest", sequence_frames(service,moment))
    original_input = {"id": moment["id"], "ordinal": moment["ordinal"], "t0_us": moment["t0_us"],
                      "reviewed": True, "frame_ids": [f["frame_id"] for f in frames],
                      "coc": deepcopy(coc), "constraints": deepcopy(original), "observation_gap": False}
    state = bundle.get("vehicle_state_input")
    original_input["vehicle_state"]=deepcopy(state)
    if state:
        original_input["frame_ids"].extend("CAN:"+str(f["sample"]["timestamp_us"]) for f in state["frames"] if f.get("sample"))
    original_input["current_evidence_refs"] = current_evidence(service,moment,state)
    assisted = bundle.get("coc_used") != coc or context.get("human_assisted_context",False)
    previous_coc=context.get("previous_coc")
    if previous_coc:
        previous_id=context.get("previous_moment_id")
        prior_input=previous.get("original_input",{}) if previous else {}
        prior_original=prior_input.get("coc") if prior_input.get("id")==previous_id else None
        assisted = assisted or previous_coc != prior_original
    original_definitions={cid:r["definition"] for cid,r in (initial or {}).get("ledger",{}).items()}
    assisted = assisted or any(original_definitions.get(d["condition_id"]) != d for d in context.get("previous_definitions",[]))
    continuation=None
    try:
        if not coc or "entities" not in coc or "new_definitions" not in original:
            raise ValueError("No modern generated pair")
        checked = child("SEQ_QUALITY", {"moments":[original_input], "catalog":context.get("catalog", {"sources": []}), "initial_summary":initial})
        continuation=checked.get("continuation_summary")
        scene = checked["scenes"][-1]
        result = {"status": scene.get("status", "REVIEW_REQUIRED"), "codes": scene.get("codes", []),
                  "source_status": scene.get("source_status"), "review_items": scene.get("review_items", []), "properties":scene.get("properties")}
    except (ValueError, StudioError) as exc:
        result = {"status": "REVIEW_REQUIRED", "codes": ["INVALID_ORIGINAL"], "message": str(exc)[:1800]}
    except subprocess.TimeoutExpired:
        result = {"status":"REVIEW_REQUIRED","codes":["QUALITY_CHECK_TIMEOUT"]}
    if assisted and result["status"] == "PASS":
        result = {**result,"logical_status":result["status"],"status":"REVIEW_REQUIRED","codes":result["codes"]+["HUMAN_ASSISTED_PAIR"]}
    record = {"moment_id": moment["id"], "ordinal": moment["ordinal"], "pair_id": digest(pair),
              "generation_ids": pair[:2], "verifier_signature": pair[2], "result": result, "human_assisted_pair": assisted,
              "original_input": original_input, "continuation_summary":continuation, "created": now()}
    with service.store.transaction():
        service.store.put("sequence_quality", record, identity)
    return record


def _quality_counts(results):
    count = {"total": len(results), "pass": 0, "contradiction": 0, "review_required": 0, "pass_rate": 0}
    for result in results:
        status = result.get("status", "REVIEW_REQUIRED")
        key = "pass" if status == "PASS" else "contradiction" if status == "CONTRADICTION" else "review_required"
        count[key] += 1
    if count["total"]: count["pass_rate"] = count["pass"] / count["total"]
    return count


def quality(service, identity):
    rows = service.store.db.execute("SELECT id FROM moments WHERE extraction=? ORDER BY ordinal LIMIT 200", (identity,))
    moments = [service.store.moment(row[0]) for row in rows]
    stage = latest_stage(service, identity, "SEQ_VERIFY")
    reviewed_scenes = {}
    if stage_current(service, stage):
        reviewed_scenes = {s.get("moment_id", s.get("id")): s for s in stage.get("result", {}).get("scenes", [])}
    items = []
    records=service.store.objects("sequence_quality")
    signature=tool_signature()
    for moment in moments:
        bundle=moment["components"].get("sequence_constraints",{}).get("payload",{})
        ids=[bundle.get("original_coc_generation_id"),bundle.get("generation_job_id")]
        candidates=[r for r in records if r.get("generation_ids")==ids]
        original=next((r for r in reversed(candidates) if r["verifier_signature"]==signature),None)
        generated=bool(bundle.get("generation_job_id") and bundle.get("original_candidate"))
        first = deepcopy(original["result"]) if original else {"status": "REVIEW_REQUIRED", "codes": ["ORIGINAL_QUALITY_PENDING" if generated else "NO_MODERN_GENERATION_PAIR"]}
        scene = reviewed_scenes.get(moment["id"])
        reviewed = deepcopy(scene) if scene and all(service.store.approved(moment,k) for k in KINDS.values()) else {"status": "REVIEW_REQUIRED", "codes": ["CURRENT_REVIEW_REQUIRED"]}
        items.append({"moment_id": moment["id"], "ordinal": moment["ordinal"],
                      "pair_id": original["pair_id"] if original else digest(ids+[signature]) if generated else None,
                      "generation_ids": original["generation_ids"] if original else ids if generated else [],
                      "human_assisted_pair": original.get("human_assisted_pair",False) if original else False,
                      "pending": generated and original is None,
                      "verifier_signature":original["verifier_signature"] if original else signature,
                      "first_pass": first, "reviewed": reviewed})
    attempted={a["job_id"] for a in service.store.objects("provider_attempt")}
    failures=sum(j["id"] in attempted and j["kind"] in ("SEQ_COC","SEQ_CONSTRAINTS")
                 and j["status"] in ("FAILED","TIMED_OUT","OUTCOME_UNKNOWN","STALE_RESULT")
                 and j["inputs"].get("moment",{}).get("extraction_id")==identity
                 for j in (service.store.job(i) for i in service.store.job_ids(statuses=("FAILED","TIMED_OUT","OUTCOME_UNKNOWN","STALE_RESULT"))))
    return {"not_generated": sum(i["pair_id"] is None for i in items),"generation_failures":failures,
            "pending":sum(i["pending"] for i in items),
            "first_pass": _quality_counts([i["first_pass"] for i in items if i["pair_id"] is not None]),
            "reviewed": _quality_counts([i["reviewed"] for i in items]), "items": items}
