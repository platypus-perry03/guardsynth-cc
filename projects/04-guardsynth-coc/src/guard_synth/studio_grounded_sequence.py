"""Project-owned bounded, qualitative CoC profile over the shared EBLC Core.

Facts are extracted claims, never certified scene truth. Only immediately prior
state and action summaries cross a scene boundary; expected future facts are not
asserted. Legal-source review is independent of logical consistency.
"""
from copy import deepcopy
import hashlib
import json
import re
import z3

from guard_synth_eblc.schema_validation import validate
from guard_synth_eblc.action_contract import var, literal, binary, conjunction, neg
from guard_synth_eblc.core_ir import parse_core_model, declaration_map
from guard_synth_eblc import smt_compiler

VERSION = "studio-grounded-sequential-coc-v0.3-properties"
ACTIONS = ["START", "STOP", "CONTINUE", "ENTER", "HOLD"]
CLASSES = ["TRAFFIC_CONTROL", "VEHICLE", "VULNERABLE_ROAD_USER", "ROAD_LAYOUT", "WORKZONE_OBSTACLE", "ROAD_SURFACE", "VISIBILITY"]
PREDICATES = ["IN", "OCCUPIES", "AHEAD_OF", "BEHIND_OF", "LEFT_OF", "RIGHT_OF", "ADJACENT_TO", "BOUNDARY_OF", "APPLIES_TO", "PATH_CONFLICT", "SIGNAL_RED", "SIGNAL_GREEN", "PATH_CLEAR", "ZONE_CLOSED", "STOPPED", "VISIBILITY_INSUFFICIENT", "SURFACE_RISK", "PASSAGE_COMPLETE"]
KINDS = ["EGO", "VEHICLE", "PEDESTRIAN", "CYCLIST", "SIGNAL", "ZONE", "LANE", "OBSTACLE", "SURFACE", "VISIBILITY"]
CONTRADICTIONS = {"RULE_CONTRADICTION", "ACTION_CONTRADICTION", "IDENTITY_CONFLICT", "OBSERVATION_CONFLICT", "RELATION_CONTRADICTION", "POSTCONDITION_CONTRADICTION", "LIFECYCLE_CONFLICT", "PRECONDITION_CONTRADICTION", "JUSTIFICATION_CONTRADICTION", "CAN_ACTION_CONTRADICTION"}


def closed(**properties):
    return {"type":"object", "properties":properties, "required":list(properties), "additionalProperties":False}


def enum(values, nullable=False):
    return {"type":["string","null"] if nullable else "string", "enum":list(values)+([None] if nullable else [])}


def array(item):
    return {"type":"array", "items":item}


def _context_ids(context, task):
    context=context or {}
    previous={e["entity_id"] for e in context.get("inherited_entities",[])+context.get("previous_entities",[])}
    current=context.get("current_entities",context.get("coc",{}).get("entities",[]))
    if isinstance(current,dict): current=current.get("entities",[])
    ids={e["entity_id"] if isinstance(e,dict) else e for e in current}
    if task=="SEQ_COC": ids={"ego"}|{"e"+str(i) for i in range(1,9)}
    else: ids.update(context.get("entity_ids",[])); ids.add("ego")
    return sorted(ids|previous),sorted(previous)


def grounded_schema(task, context=None):
    s={"type":"string"};n={"type":["string","null"]}
    ids,previous=_context_ids(context,task)
    ref=enum(ids) if context is not None else s
    nullable_ref=enum(ids,True) if context is not None else n
    evidence=context.get("evidence_refs",context.get("evidence_ids")) if context is not None else None
    evidence_ref=enum(evidence) if evidence else s
    refs=array(s);evidence_refs=array(evidence_ref)
    atom=closed(predicate=enum(PREDICATES),subject_ref=ref,object_ref=nullable_ref)
    guard=closed(atom=atom,expected_truth=enum(["TRUE","FALSE"]))
    truth=enum(["TRUE","FALSE","UNKNOWN","CONFLICT"])
    if task=="SEQ_COC":
        entity=closed(entity_id=ref,kind=enum(KINDS),description=s,identity_status=enum(["NEW_LOCAL","MATCHED_PREVIOUS","UNCERTAIN"]),previous_entity_ref=enum(previous,True) if context is not None else n,evidence_refs=evidence_refs)
        relation=closed(subject_ref=ref,predicate=enum(PREDICATES),object_ref=nullable_ref,truth=truth,evidence_refs=evidence_refs)
        action=closed(code=enum(ACTIONS),subject_ref=enum(["ego"]),action_target_ref=nullable_ref,movement_ref=nullable_ref,evidence_refs=evidence_refs)
        binding=closed(action_index={"type":"integer","enum":[0,1,2,3,4]},explanation_excerpt=s,reasons=array(guard))
        return closed(entities=array(entity),relations=array(relation),observed_actions=array(action),observations=s,explanation=s,unknowns=array(s),evidence_refs=evidence_refs,reason_bindings=array(binding),action_observation_complete={"type":"boolean"})
    if task!="SEQ_CONSTRAINTS": raise ValueError("Unknown sequence task")
    definition=closed(condition_id=s,condition_class=enum(CLASSES,True),subject_ref=enum(["ego"]),condition_target_refs=array(ref),action_target_ref=nullable_ref,movement_ref=nullable_ref,description=s,effect=enum(["FORBID","REQUIRE","ALLOW"]),actions=array(enum(ACTIONS)),activation_all_of=array(guard),release_any_of=array(guard),preconditions=array(guard),expected_postconditions=array(guard),source_refs=refs)
    definition["properties"]["postcondition_window"]=enum(["UNSPECIFIED","NEXT_OBSERVATION"])
    definition["required"].append("postcondition_window")
    fact=closed(atom=atom,truth=truth,evidence_refs=evidence_refs,evidence_note=s)
    return closed(new_definitions=array(definition),facts=array(fact),unresolved_previous_condition_refs=refs,unknowns=array(s))


def grounded_instructions(task):
    from .studio_relations import grammar
    extensions = " reason_bindings로 explanation의 실제 원문 일부(explanation_excerpt), observed_actions의 0부터 시작하는 action_index, 해당 행동을 설명하는 reasons 원자를 연결한다. 이유 원자의 참 여부는 relations/facts의 관찰 근거로 별도 확인한다. 이유를 확인할 수 없으면 reasons를 추측하지 말고 빈 reason_bindings로 남긴다. action_observation_complete는 목록 밖 행동의 미수행까지 현재 관찰 구간에서 확인했을 때만 true이며 보통 false다." if task=="SEQ_COC" else " postcondition_window는 기본 UNSPECIFIED다. 실제 행동의 완료를 바로 다음 관찰에서 확인할 근거가 있을 때만 NEXT_OBSERVATION을 쓴다. 녹색/ALLOW나 임의의 다음 썸네일을 완료 시한으로 만들지 않는다."
    common=" 한국어로 작성한다. 현재와 바로 이전 영상 및 제공 CAN만 사용한다. CAN age_us/null과 측정 단위를 존중한다. CAN 조향 부호로 좌우를 단정하지 않는다. CAN은 ego 정지/주행 관찰을 뒷받침할 수 있지만 신호 색, 타차/보행자 경로 충돌, 공간 관계나 실제 영역 진입을 증명하지 않으므로 해당 사실/ENTER에는 현재 영상 근거가 필요하다. evidence_refs는 제공 frame_id 또는 CAN:<timestamp_us>만 쓴다. 신호 적용성 APPLIES_TO(signal,ego 또는 lane/zone)와 색 SIGNAL_RED/GREEN(signal,null)은 분리한다. PATH_CONFLICT(actor 또는 obstacle/zone,ego 또는 lane/zone)는 경로 충돌, IN/OCCUPIES(actor,lane/zone)는 점유다. PATH_CLEAR/ZONE_CLOSED(lane/zone,null), STOPPED(actor,null), PASSAGE_COMPLETE(ego,zone 또는 null), VISIBILITY_INSUFFICIENT/SURFACE_RISK(대상,ego 또는 null)을 사용한다. 관계는 subject 기준: LEFT_OF(A,B)는 A가 B 왼쪽, AHEAD_OF(A,ego)는 A가 앞이다. IN/점유와 PATH_CONFLICT는 다르며 길가에 보인다고 실제 경로 충돌 TRUE가 아니다. 확인 못한 원자는 UNKNOWN이다. 거리/TTC/새 predicate/법조문을 만들지 않는다."
    common += " observation_scope.current_frame_id의 CURRENT 영상이 지금 검토하는 장면이다. PREVIOUS_COMPARISON 영상은 자차 움직임 변화와 기존 제약의 유지 여부를 비교하는 용도다. 먼저 CURRENT만 보고 현재 대상·관찰·공간 관계를 정한 다음 이전 영상과 변화를 비교한다. entities에는 CURRENT에서 식별되는 대상만 포함하고 각 대상의 evidence_refs에 실제 현재 영상 ID를 연결한다(ego 정지·주행은 현재 CAN도 가능). 이전 영상에만 보이는 표지·신호·보행자·물체를 현재 대상 목록, 현재 관찰, 설명 또는 불확실 목록에 새로 끌어오지 않는다. 과거 전용 대상을 현재 영상 ID로 바꾸어 인용하지 않는다. 현재 영상에 없는 이전 대상은 previous_entities/previous_definitions로만 다루고, 실제 이어받을 기존 제약이 없으면 언급하지 않는다. 이어받은 활성 제약은 대상이 안 보인다는 이유로 삭제/해제하지 말고 UNKNOWN 또는 unresolved_previous_condition_refs로 남긴다. 현재 공간 사실의 TRUE/FALSE에는 현재 영상 근거가 필요하며 이전 영상만으로 현재 값을 단정하지 않는다. 본문은 현재 장면의 행동 이유를 설명하고 과거에만 보이는 불필요한 표지의 적용성 질문을 반복하지 않는다."
    common += " 관계 문법: " + json.dumps(grammar(), ensure_ascii=False) + " 단일 상태의 object_ref는 null이다. 모든 방향은 현재 자차 진행 방향을 공통 기준으로 사용한다. ADJACENT_TO(A,B)는 ADJACENT_TO(B,A)와 같고, IN/BOUNDARY_OF/APPLIES_TO는 대상을 뒤집지 않는다. 제공 CoC의 ID와 대상 의미를 그대로 사용하고 새로 번호를 매기지 않는다."
    common += " inherited_entities는 이어받은 제약에 연결된 대상의 종류·이름 정보이며 현재 관찰이나 사실이 아니다. 현재 entities에 없는 대상도 기존 제약의 유지·해제를 검사할 때 이 ID를 참조할 수 있다. 현재 근거로 확인할 수 없으면 UNKNOWN으로 남기고 현재 대상 목록에 억지로 추가하지 않는다. 같은 ID를 다른 대상에 재사용하지 않는다."
    common += extensions
    if task=="SEQ_COC":
        return "실제 기록된 운전 CoC 초안을 추출한다. 최대 8 entity, 8 relation. ego는 EGO, 다른 대상은 제공 익명 ID를 쓴다. 동일 대상을 확인한 경우만 이전 ID와 MATCHED_PREVIOUS를 사용한다. 이전 장면이 없는 부분 시작은 움직임을 추정하지 않는다. observed_actions에는 ego 실제 행동만 쓰고 타차 움직임은 observations/relations에 쓴다. START는 정지에서 출발, STOP은 정지 동작, HOLD는 이미 정지 유지, CONTINUE는 주행 지속, ENTER는 구체 대상에 실제 진입 확인이다. ENTER의 action_target_ref는 반드시 확인된 영역이다. 차로와 공사 영역은 구분한다. 녹색을 진입 명령이나 실제 진입 증거로 쓰지 않는다. 설명은 3문장 이내, unknowns에 가림과 미확인 관계를 남긴다."+common
    if task!="SEQ_CONSTRAINTS": raise ValueError("Unknown sequence task")
    return "영상/CAN/CoC 초안에서 제약 검토 후보를 추출한다. CoC는 독립 증거가 아니며 영상이 우선이다. 최대 4 신규 definition, 24 facts, 제공 seven class만 쓰며 불확실 분류는 null. subject는 ego, condition_target_refs는 원인 대상, action_target_ref는 적용 차로/영역으로 구분하고 실제 현재/이전 entity만 참조한다. 관찰 행동을 권고/의무로 바꾸지 않는다. 선행차가 보인다고 REQUIRE CONTINUE/HOLD를 쓰지 않는다. 녹색은 ALLOW 후보이며 REQUIRE ENTER가 아니다. 진입/출발 preconditions에 실제 PATH_CLEAR 및 필요한 신호 적용성을 남긴다. 정의와 현재 facts를 분리한다. activation_all_of 전부 충족시 활성, release_any_of 하나 충족시 해제. guard.expected_truth는 원자에 요구되는 TRUE/FALSE, facts.truth는 원자 자체의 현재 값이다. 미확인을 FALSE/해제로 바꾸지 않는다. 이전 definitions는 불변으로 유지되므로 다시 쓰거나 동일 ID로 바꾸지 말고 facts만 갱신한다. 재확인 불가시 UNKNOWN 또는 unresolved_previous_condition_refs에 남긴다. 이전 ACTIVE는 확인된 해제 없이 유지된다. 횡단보도·교차로 진입 제약은 적용 영역을 명시하고, 그 영역을 실제 통과한 근거가 있을 때 PASSAGE_COMPLETE(ego,zone)=TRUE로 해제할 수 있게 한다. 신호나 보행자가 현재 보이지 않는 것만으로 해제하지 않는다. IN(ego,zone)=FALSE만으로 통과 완료를 추정하지 않는다(진입 전에도 FALSE일 수 있음). 지나온 영역의 신호 적용성 미확인을 앞으로의 모든 진입 금지로 확장하지 않는다. 다른 구간의 양보 표지·우선순위는 별도 대상으로 검토한다. expected_postconditions는 이후 확인할 기대값이며 현재 사실을 강제하지 않는다. FORBID ENTER 기대 결과는 진입 FALSE이며 ALLOW는 완료 의무가 아니다. 제공 법 원문 없는 경우 source_refs=[]로 남긴다. description/evidence_note는 각각 한 문장."+common


def validate_grounded(task, data, frame_ids, source_ids, context=None):
    # Old saved candidates remain byte-for-byte intact. Missing extensions mean
    # unbound reasons, incomplete observation and unspecified completion time.
    checked=deepcopy(data)
    if task=="SEQ_COC":
        checked.setdefault("reason_bindings",[]);checked.setdefault("action_observation_complete",False)
    else:
        for d in checked.get("new_definitions",[]):d.setdefault("postcondition_window","UNSPECIFIED")
    validate(checked,grounded_schema(task,context))
    if task=="SEQ_COC" and (len(checked["reason_bindings"])>5 or any(len(b["reasons"])>8 for b in checked["reason_bindings"])):
        raise ValueError("At most 5 reason bindings and 8 reasons per binding")
    evidence=set(frame_ids)
    if context: evidence.update(context.get("evidence_refs",context.get("evidence_ids",[])))
    def walk(value):
        if isinstance(value,dict):
            if "evidence_refs" in value and not set(value["evidence_refs"]).issubset(evidence): raise ValueError("Evidence must refer to supplied causal evidence IDs")
            for item in value.values(): walk(item)
        elif isinstance(value,list):
            for item in value: walk(item)
    walk(data)
    if task=="SEQ_COC":
        if len(data["entities"])>9 or len(data["relations"])>8 or len(data["observed_actions"])>5: raise ValueError("CoC bounded entity/relation/action count exceeded")
        ids=[e["entity_id"] for e in data["entities"]]
        if len(ids)!=len(set(ids)): raise ValueError("Duplicate entity ID")
        available=set(ids)|{"ego"}|{e["entity_id"] for e in (context or {}).get("inherited_entities",[])+(context or {}).get("previous_entities",[])}
        for item in data["relations"]+data["observed_actions"]:
            for key in ("subject_ref","object_ref","action_target_ref","movement_ref"):
                if item.get(key) is not None and item[key] not in available: raise ValueError("Entity ID was not supplied")
        for a in data["observed_actions"]:
            if a["code"]=="ENTER" and not a["action_target_ref"]: raise ValueError("ENTER requires a concrete action target")
    else:
        if len(data["new_definitions"])>4 or len(data["facts"])>24: raise ValueError("At most 4 definitions and 24 facts per moment")
        seen=set()
        for d in data["new_definitions"]:
            cid=d["condition_id"]
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",cid) or cid in seen: raise ValueError("Invalid or duplicate stable condition ID")
            seen.add(cid)
            if not d["description"].strip() or not d["actions"] or len(d["actions"])!=len(set(d["actions"])): raise ValueError("Description and unique target actions required")
            if not set(d["source_refs"]).issubset(source_ids): raise ValueError("Source ID was not supplied")
    return deepcopy(data)


def atom_key(a):
    return (a["predicate"],a["subject_ref"],a["object_ref"])


def symbol(prefix, value):
    return prefix+hashlib.sha256(repr(value).encode()).hexdigest()[:20]


def source(moment,component,path,value):
    return {"moment_id":moment["id"],"component":component,"path":path,"value":deepcopy(value),"evidence_refs":deepcopy(value.get("evidence_refs",[]) if isinstance(value,dict) else [])}


def status(codes):
    return "CONTRADICTION" if set(codes)&CONTRADICTIONS else "REVIEW_REQUIRED" if codes else "PASS"


def aggregate(values, all_of):
    if "CONFLICT" in values:return "CONFLICT"
    if ("FALSE" if all_of else "TRUE") in values:return "FALSE" if all_of else "TRUE"
    if not values:return "UNKNOWN" if all_of else "FALSE"
    if "UNKNOWN" in values:return "UNKNOWN"
    return "TRUE" if all_of else "FALSE"


def guard_truth(g, facts):
    truth=facts.get(atom_key(g["atom"]),"UNKNOWN")
    return truth if truth in ("UNKNOWN","CONFLICT") else "TRUE" if truth==g["expected_truth"] else "FALSE"


def _supported_atom(key,kinds):
    from .studio_relations import atom_error
    p,a,b=key
    return atom_error({"predicate":p,"subject_ref":a,"object_ref":b}, {ref:{"kind":kind} for ref,kind in kinds.items()}) is None


def _supports_evidence(key,refs,current_evidence):
    current=set(refs) if current_evidence is None else set(current_evidence)
    supplied=set(refs)&current
    if key==("STOPPED","ego",None):return bool(supplied)
    return any(not ref.startswith("CAN:") for ref in supplied)


def _uncertain_entities(current_entities,previous_entities):
    previous={e["entity_id"]:e for e in previous_entities};uncertain=set()
    for e in current_entities:
        old=previous.get(e["entity_id"]);matched=e["identity_status"]=="MATCHED_PREVIOUS"
        invalid=(matched and (not old or e["previous_entity_ref"]!=old["entity_id"] or e["kind"]!=old["kind"])) or (old and e["entity_id"]!="ego" and e["identity_status"]=="NEW_LOCAL")
        if e["identity_status"]=="UNCERTAIN" or invalid:uncertain.add(e["entity_id"])
    return uncertain


def _merge_truth(facts,key,truth):
    if key in facts and facts[key]!=truth and {facts[key],truth}<={"TRUE","FALSE","CONFLICT"}:facts[key]="CONFLICT"
    elif truth!="UNKNOWN" or key not in facts:facts[key]=truth


def _semantic_key(core):
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ("source_refs","model_id","description")}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(clean(core),sort_keys=True,separators=(",",":")).encode()).hexdigest()


def _next_state(activation,release,prior):
    if activation=="CONFLICT" or release=="CONFLICT" or activation==release=="TRUE":return "CONFLICT"
    if release=="TRUE":return "RELEASED"
    if activation=="TRUE" or prior=="ACTIVE":return "ACTIVE"
    if activation=="FALSE" and prior!="UNKNOWN":return "INACTIVE"
    return "UNKNOWN"


def definition_entities(definition, entities):
    """Keep only target identity metadata; never retain observations or evidence."""
    refs={definition.get(k) for k in ("subject_ref","action_target_ref","movement_ref")}
    refs.update(definition.get("condition_target_refs",[]))
    for field in ("activation_all_of","release_any_of","preconditions","expected_postconditions"):
        for guard in definition.get(field,[]):
            refs.update(guard["atom"].get(k) for k in ("subject_ref","object_ref"))
    return {e["entity_id"]:{k:e[k] for k in ("entity_id","kind","description")} for e in entities if e["entity_id"] in refs}


def inherited_entities(ledger):
    return list({ref:e for r in ledger.values() for ref,e in r.get("target_entities",{}).items()}.values())


def grounded_state_summary(previous_definitions, previous_states, current_constraints, current_evidence=None, current_coc=None, previous_entities=None, inherited_entities=None):
    """Advance the same bounded claim/state summary without constructing Core."""
    if len(previous_definitions)>64:raise ValueError("At most 64 stable conditions per event")
    coc=current_coc or {};previous_entities=(inherited_entities or [])+(previous_entities or [])
    kinds={e["entity_id"]:e["kind"] for e in previous_entities+coc.get("entities",[])};kinds.setdefault("ego","EGO")
    uncertain=_uncertain_entities(coc.get("entities",[]),previous_entities)
    claims=[(r,r["truth"],r["evidence_refs"],True) for r in coc.get("relations",[])]+[(f["atom"],f["truth"],f["evidence_refs"],bool(f["evidence_note"].strip())) for f in current_constraints.get("facts",[])]
    facts={}
    for a,truth,refs,note in claims:
        key=atom_key(a);valid=bool(refs and note)
        valid=valid and _supports_evidence(key,refs,current_evidence)
        if key[1] in uncertain or key[2] in uncertain or (current_coc is not None and not _supported_atom(key,kinds)):valid=False
        _merge_truth(facts,key,truth if valid else "UNKNOWN")
    states={}
    for d in previous_definitions:
        cid=d["condition_id"];prior=previous_states.get(cid,"UNKNOWN")
        if isinstance(prior,dict):prior="ACTIVE" if prior.get("active_obligation") else prior.get("state","UNKNOWN")
        activation=aggregate([guard_truth(g,facts) for g in d["activation_all_of"]],True)
        release=aggregate([guard_truth(g,facts) for g in d["release_any_of"]],False)
        state=_next_state(activation,release,prior)
        states[cid]={"state":state,"active_obligation":True} if state=="CONFLICT" and prior=="ACTIVE" else state
    return states


class CoreBuilder:
    """Source-mapped Core clauses; the platform owns lowering to Z3."""
    def __init__(self, ordinal):
        self.core={"grammar_version":"eblc-core-v0.1","model_id":"grounded_"+str(ordinal),"horizon":2,"source_refs":["profile"],"claim_scope":"CONDITIONAL_STATEMENT_CONSISTENCY_NOT_SCENE_TRUTH","declarations":[],"clauses":[],"queries":[]}
        self.names=set();self.source_map={};self.ref_cache={}
        self.declare("profile_recorded")
        self.clause("conditional_profile", literal(True))
    def refs(self,sources):
        refs=[]
        for s in sources:
            key=self.ref_cache.get(id(s))
            if key is None:
                key=symbol("source_",s);self.ref_cache[id(s)]=key
            self.source_map[key]=s
            if key not in self.core["source_refs"]:self.core["source_refs"].append(key)
            refs.append(key)
        return refs or ["profile"]
    def declare(self,name,sources=(),sort="BOOL"):
        if name not in self.names:
            self.names.add(name);self.core["declarations"].append({"name":name,"sort":sort,"time_varying":False,"enum_name":None,"enum_values":[],"unit":None,"frame":None,"source_refs":self.refs(sources)})
        return var(name)
    def clause(self,cid,formula,sources=(),kind="ASSUMPTION"):
        self.core["clauses"].append({"id":cid,"kind":kind,"enforcement":"INITIAL","formula":formula,"source_refs":self.refs(sources),"description":cid})
    def query(self,qid,formula,sources=()):
        self.core["queries"].append({"id":qid,"formula":formula,"expected":"SAT","classification":"CONSISTENCY","source_refs":self.refs(sources),"description":qid})
    def atom(self,key,sources=()):return self.declare(symbol("atom_",key),sources)
    def guard(self,g,facts,sources=()):
        if facts.get(atom_key(g["atom"]),"UNKNOWN") in ("UNKNOWN","CONFLICT"):return literal(False)
        value=self.atom(atom_key(g["atom"]),sources)
        return value if g["expected_truth"]=="TRUE" else neg(value)


def _bounded_solve(core):
    """Use shared Core parsing/lowering with a per-query 1000ms Z3 bound."""
    compiled=smt_compiler.compile_core_model(parse_core_model(core));results=[]
    solver=z3.Solver();solver.set(timeout=1000);tracked={}
    for i,r in enumerate(compiled.assertions):
        label=z3.Bool("assertion_"+str(i));tracked[str(label)]=r
        solver.assert_and_track(r.expression,label)
    for query in compiled.model.queries:
        lowered=smt_compiler._lower(query.formula,base_time=0,model=compiled.model,declarations=declaration_map(compiled.model),symbols=compiled.symbols,enum_codes=compiled.enum_codes)
        solver.push();solver.add(*lowered.side_constraints,lowered.term)
        checked=solver.check();result="SAT" if checked==z3.sat else "UNSAT" if checked==z3.unsat else "UNKNOWN"
        refs=list(query.source_refs);clauses=[]
        if result=="UNSAT":
            records=[tracked[str(label)] for label in solver.unsat_core()]
            refs=sorted(set(ref for r in records for ref in r.source_refs)|set(query.source_refs));clauses=sorted({r.clause_id for r in records})
        results.append({"query_id":query.query_id,"status":result,"expected":query.expected,"matches_expected":result==query.expected,"source_refs":refs,"unsat_clause_ids":clauses,"reason_unknown":solver.reason_unknown() if result=="UNKNOWN" else None})
        solver.pop()
    return {"model_id":core["model_id"],"engine":"Z3_BOUNDED_SMT","z3_version":z3.get_version_string(),"grammar_version":core["grammar_version"],"compiler_version":smt_compiler.COMPILER_VERSION,"query_count":len(results),"results":results}


def compile_grounded_sequence(moments, catalog, initial_summary=None):
    if not 1<=len(moments)<=200:raise ValueError("Verify 1–200 ordered moments")
    if [m["ordinal"] for m in moments]!=sorted(set(m["ordinal"] for m in moments)) or any(b["t0_us"]<=a["t0_us"] for a,b in zip(moments,moments[1:])):raise ValueError("Moments must be unique and chronological")
    catalog_sources={s["id"]:s for s in catalog.get("sources",[])}
    initial=deepcopy(initial_summary or {})
    ledger=initial.get("ledger",{});scenes=[];pairs=[];previous_entities=initial.get("previous_entities",[]);previous_actions=initial.get("previous_actions",[]);previous_moment=initial.get("previous_moment");previous_details=initial.get("previous_details",{});validated=set()
    if len(ledger)>64:raise ValueError("At most 64 stable conditions per event")
    if previous_moment and (moments[0]["ordinal"]<=previous_moment["ordinal"] or moments[0]["t0_us"]<=previous_moment["t0_us"]):raise ValueError("Continuation must follow its immediately previous moment")
    for m in moments:
        coc=m.get("coc") or {};con=m.get("constraints") or {}
        # An off-screen target remains part of its constraint's definition, not
        # part of the current scene's observed entities or facts.
        for r in ledger.values():
            r.setdefault("target_entities",definition_entities(r["definition"],previous_entities))
        retained=inherited_entities(ledger)
        identity_entities=list({e["entity_id"]:e for e in retained+previous_entities}.values())
        codes=set();review=[];builder=CoreBuilder(m["ordinal"])
        def finding(code,message,sources=()):
            codes.add(code);review.append({"code":code,"message":message,"sources":deepcopy(list(sources))})
        structured="entities" in coc and "new_definitions" in con
        if not structured:
            finding("LEGACY_INPUT_GAP","구조화된 CoC와 제약을 현재 장면에서 검토해야 합니다.",[source(m,"sequence_coc","",coc),source(m,"sequence_constraints","",con)])
        else:
            context={"coc":coc,"previous_entities":previous_entities,"inherited_entities":retained}
            evidence=set(m.get("frame_ids",[]))|set(m.get("evidence_refs",[]))|set(m.get("evidence_ids",[]))
            context["evidence_refs"]=sorted(evidence)
            validate_grounded("SEQ_COC",coc,evidence,set(catalog_sources),context if identity_entities else None)
            # Missing legal IDs remain source review, not fabricated grounding.
            validate_grounded("SEQ_CONSTRAINTS",con,evidence,set(catalog_sources)|{s for d in con["new_definitions"] for s in d["source_refs"]},context)
        actions=coc.get("observed_actions",[]) if structured else []
        action_sources=[source(m,"sequence_coc","/observed_actions/"+str(i),a) for i,a in enumerate(actions)]
        if not structured or not m.get("reviewed") or not actions or not coc.get("evidence_refs"):
            finding("REVIEW_REQUIRED","관찰 행동, 근거와 사람 검토가 필요합니다.",action_sources)
        if m.get("observation_gap"):finding("OBSERVATION_GAP","바로 이전 관찰과 시간 연속성을 확인해야 합니다.")
        notes=[{"code":"EXTRACTION_LIMITATION","message":text} for text in (coc.get("unknowns",[])+con.get("unknowns",[]))] if structured else []
        uncertain=_uncertain_entities(coc.get("entities",[]) if structured else [],identity_entities)
        for i,e in enumerate(coc.get("entities",[]) if structured else []):
            if e["entity_id"] in uncertain:finding("ENTITY_IDENTITY_UNCERTAIN","이전 조건 대상과 현재 대상의 동일성이 확인되지 않았습니다.",[source(m,"sequence_coc","/entities/"+str(i),e)])
        carried=sorted(cid for cid,r in ledger.items() if r["state"]!="RELEASED")
        prior_states={cid:"ACTIVE" if r.get("active_obligation") else r["state"] for cid,r in ledger.items()}
        for i,d in enumerate(con.get("new_definitions",[]) if structured else []):
            ds=source(m,"sequence_constraints","/new_definitions/"+str(i),d);cid=d["condition_id"]
            if cid in ledger:
                if d!=ledger[cid]["definition"]:finding("IDENTITY_CONFLICT","이전 조건 ID의 정의가 변경되었습니다.",[ledger[cid]["source"],ds])
                else:finding("DEFINITION_REPEATED","이전 정의를 재작성하지 말고 현재 사실만 갱신해야 합니다.",[ds])
            else:
                if len(ledger)>=64:raise ValueError("At most 64 stable conditions per event")
                ledger[cid]={"definition":deepcopy(d),"source":ds,"state":"UNKNOWN",
                             "target_entities":definition_entities(d,identity_entities+coc.get("entities",[]))}
        if not ledger:finding("EMPTY_CONSTRAINTS","검토할 구조화 제약이 없습니다.",[source(m,"sequence_constraints","/new_definitions",con.get("new_definitions",[]))])
        for cid in con.get("unresolved_previous_condition_refs",[]) if structured else []:
            finding("UNRESOLVED_PREVIOUS" if cid in ledger else "PRIOR_CONTEXT_MISSING","이전 조건의 현재 근거를 확인할 수 없습니다.",[source(m,"sequence_constraints","/unresolved_previous_condition_refs",con["unresolved_previous_condition_refs"])])
        current_evidence=set(m.get("current_evidence_refs",m.get("current_frame_ids",m.get("frame_ids",[]))))
        claims=[];facts={};fact_sources={}
        for i,r in enumerate(coc.get("relations",[]) if structured else []):
            claims.append((atom_key(r),r["truth"],source(m,"sequence_coc","/relations/"+str(i),r),_supports_evidence(atom_key(r),r["evidence_refs"],current_evidence)))
        for i,f in enumerate(con.get("facts",[]) if structured else []):
            src=source(m,"sequence_constraints","/facts/"+str(i),f)
            claims.append((atom_key(f["atom"]),f["truth"],src,bool(_supports_evidence(atom_key(f["atom"]),f["evidence_refs"],current_evidence) and f["evidence_note"].strip())))
        entity_kinds={e["entity_id"]:e["kind"] for e in inherited_entities(ledger)+previous_entities+(coc.get("entities",[]) if structured else [])};entity_kinds.setdefault("ego","EGO")
        for i,(key,truth,src,grounded) in enumerate(claims):
            fact_sources.setdefault(key,[]).append(src)
            if key[1] in uncertain or key[2] in uncertain:truth="UNKNOWN"
            if not _supported_atom(key,entity_kinds):
                finding("UNSUPPORTED_ATOM","원자 대상 종류 또는 단항/이항 관계가 지원 의미와 맞지 않습니다.",[src]);truth="UNKNOWN"
            if not grounded:
                finding("EVIDENCE_MISSING","사실의 인과적 근거가 없어 UNKNOWN으로 처리합니다.",[src]);truth="UNKNOWN"
            _merge_truth(facts,key,truth)
            if facts[key]=="CONFLICT":finding("OBSERVATION_CONFLICT","동일 원자의 관찰값이 충돌합니다.",fact_sources[key])
            av=builder.atom(key,[src])
            if truth in ("TRUE","FALSE"):builder.clause("claim_"+str(i),binary("eq",av,literal(truth=="TRUE")),[src])
            elif truth=="CONFLICT":builder.clause("claim_conflict_"+str(i),literal(False),[src]);finding("OBSERVATION_CONFLICT","원본 사실이 CONFLICT로 표시되었습니다.",[src])
        inverse={"LEFT_OF":"RIGHT_OF","RIGHT_OF":"LEFT_OF","AHEAD_OF":"BEHIND_OF","BEHIND_OF":"AHEAD_OF"}
        spatial_sources=deepcopy(fact_sources)
        for r in ledger.values():
            for g in r["definition"]["activation_all_of"]+r["definition"]["release_any_of"]+r["definition"]["preconditions"]+r["definition"]["expected_postconditions"]:
                spatial_sources.setdefault(atom_key(g["atom"]),[]).append(r["source"])
        for key,srcs in list(spatial_sources.items()):
            p,a,b=key
            if p=="ADJACENT_TO" and _supported_atom(key,entity_kinds):
                reverse=(p,b,a)
                builder.clause(symbol("adjacent_symmetric_",key),binary("eq",builder.atom(key),builder.atom(reverse)),srcs+fact_sources.get(reverse,[]))
            if p in inverse:
                axis="lateral_" if p in ("LEFT_OF","RIGHT_OF") else "longitudinal_"
                left=builder.declare(symbol(axis,a),srcs,"INT");right=builder.declare(symbol(axis,b),srcs,"INT")
                order=binary("lt" if p in ("LEFT_OF","BEHIND_OF") else "gt",left,right)
                builder.clause(symbol("direction_order_",key),binary("eq",builder.atom(key),order),srcs)
                same_reverse=(p,b,a);opposite=(inverse[p],a,b);inverse_reverse=(inverse[p],b,a)
                builder.clause(symbol("direction_exclusive_",key),neg(conjunction(builder.atom(key),builder.atom(same_reverse))),srcs+fact_sources.get(same_reverse,[]))
                builder.clause(symbol("direction_opposite_",key),neg(conjunction(builder.atom(key),builder.atom(opposite))),srcs+fact_sources.get(opposite,[]))
                builder.clause(symbol("direction_inverse_",key),binary("eq",builder.atom(key),builder.atom(inverse_reverse)),srcs+fact_sources.get(inverse_reverse,[]))
        relation_core=deepcopy(builder.core);relation_core["queries"]=[]
        relation_core["queries"].append({"id":"relation_consistency","formula":literal(True),"expected":"SAT","classification":"CONSISTENCY","source_refs":["profile"],"description":"Directional observation consistency"})
        # Source refs added after snapshot must also exist in the snapshot.
        relation_core["source_refs"]=deepcopy(builder.core["source_refs"])
        all_action_keys={tuple(a.get(k) for k in ("code","subject_ref","action_target_ref","movement_ref")) for a in actions}
        rule_sources=[];checks=[];source_review=[];states={};postcondition_checks=[]
        for cid,r in ledger.items():
            d=r["definition"];ds=r["source"];prior=prior_states.get(cid,"UNKNOWN")
            activation=aggregate([guard_truth(g,facts) for g in d["activation_all_of"]],True)
            release=aggregate([guard_truth(g,facts) for g in d["release_any_of"]],False)
            pre=aggregate([guard_truth(g,facts) for g in d["preconditions"]],True) if d["preconditions"] else "TRUE"
            state=_next_state(activation,release,prior)
            lifecycle_sources=[s for g in d["activation_all_of"]+d["release_any_of"] for s in fact_sources.get(atom_key(g["atom"]),[])]
            if state=="CONFLICT":finding("LIFECYCLE_CONFLICT","활성/해제 조건이 동시에 성립하거나 근거가 충돌합니다.",[ds]+lifecycle_sources)
            r["state"]=state;r["active_obligation"]=state=="ACTIVE" or (state=="CONFLICT" and prior=="ACTIVE");states[cid]={"active_obligation":r["active_obligation"],"state":state,"prior_state":prior,"activation_guard":activation,"release_guard":release,"precondition_guard":pre,"carried_active_without_confirmed_release":prior=="ACTIVE" and release!="TRUE" and state=="ACTIVE","permission_confirmed":d["effect"]=="ALLOW" and state=="ACTIVE" and activation=="TRUE" and release=="FALSE" and pre=="TRUE"}
            gs=[s for g in d["activation_all_of"]+d["release_any_of"]+d["preconditions"] for s in fact_sources.get(atom_key(g["atom"]),[])]
            if "ENTER" in d["actions"] and entity_kinds.get(d["action_target_ref"]) not in ("ZONE","LANE"):
                finding("UNSUPPORTED_ACTION_TARGET","진입 행동의 대상은 확인된 영역 또는 차로여야 합니다.",[ds]);states[cid]["permission_confirmed"]=False
            targets={d["subject_ref"]}|set(d["condition_target_refs"])|{ref for ref in (d["action_target_ref"],d["movement_ref"]) if ref is not None}
            if not targets.issubset(entity_kinds):finding("UNBOUND_TARGET","제약을 정의할 때 연결한 대상 정보를 찾을 수 없습니다. 현재 영상에 보이지 않는다는 뜻은 아닙니다.",[ds])
            for g in d["activation_all_of"]+d["release_any_of"]+d["preconditions"]+d["expected_postconditions"]:
                if not _supported_atom(atom_key(g["atom"]),entity_kinds):finding("UNSUPPORTED_ATOM","정의의 원자가 지원되는 관계/대상 종류와 맞지 않습니다.",[ds])
            if activation=="UNKNOWN" or release=="UNKNOWN" or state=="UNKNOWN":finding("EVIDENCE_MISSING","조건의 현재 활성 또는 해제 근거가 미확인입니다.",[ds]+gs)
            matching_action=any(a["code"] in d["actions"] and all(a.get(k)==d.get(k) for k in ("subject_ref","action_target_ref","movement_ref")) for a in actions)
            if d["effect"]!="FORBID" and state=="ACTIVE" and matching_action and pre in ("UNKNOWN","CONFLICT"):finding("PRECONDITION_UNKNOWN","행동 선행 조건이 확인되지 않았습니다.",[ds]+gs)
            if d["condition_class"] is None or not d["activation_all_of"] or not d["release_any_of"] or ("ENTER" in d["actions"] and not d["action_target_ref"]):finding("UNSUPPORTED_CONDITION","분류, 활성/해제 또는 구체 행동 대상을 검토해야 합니다.",[ds])
            if not d["source_refs"] or any(s not in catalog_sources or not catalog_sources[s].get("reviewed") for s in d["source_refs"]):source_review.append({"condition_id":cid,"code":"UNGROUNDED","sources":[ds]})
            prev=builder.declare(symbol("previous_",cid),[ds]);active=builder.declare(symbol("active_",cid),[ds])
            if prior!="UNKNOWN":builder.clause(cid+"_prior",binary("eq",prev,literal(prior=="ACTIVE")),[ds])
            on=conjunction(*(builder.guard(g,facts,[ds]) for g in d["activation_all_of"])) if d["activation_all_of"] else literal(False)
            clear=neg(conjunction(*(neg(builder.guard(g,facts,[ds])) for g in d["release_any_of"]))) if d["release_any_of"] else literal(False)
            transition={"op":"ite","condition":clear,"then":literal(False),"else":{"op":"ite","condition":on,"then":literal(True),"else":prev}}
            builder.clause(cid+"_transition",binary("eq",active,transition),[ds]+gs,"LIFECYCLE")
            formulas=[]
            for action in d["actions"]:
                key=(action,d["subject_ref"],d["action_target_ref"],d["movement_ref"])
                av=builder.declare(symbol("action_",key),[ds])
                outcome=neg(av) if d["effect"]=="FORBID" else av
                if d["effect"]!="ALLOW":
                    rule=binary("implies",active,outcome);formulas.append(rule);builder.clause(cid+"_"+action.lower(),rule,[ds]+gs,"INVARIANT")
                if d["effect"]!="FORBID" and state=="ACTIVE" and pre=="FALSE" and key in all_action_keys:finding("PRECONDITION_CONTRADICTION","기록 행동의 선행 조건이 거짓입니다.",[ds]+action_sources+gs)
            checks.append((cid,formulas,[ds]+gs+action_sources));rule_sources.append(ds)
            if d["expected_postconditions"]:
                matched_previous=any(a["code"] in d["actions"] and all(a.get(k)==d.get(k) for k in ("subject_ref","action_target_ref","movement_ref")) for a in previous_actions)
                prior_detail=previous_details.get(cid,{})
                previous_permitted=d["effect"]!="ALLOW" or (prior_detail.get("permission_confirmed") and prior_detail.get("precondition_guard")=="TRUE")
                previous_relevant=bool(previous_moment and prior=="ACTIVE" and matched_previous)
                current_relevant=state=="ACTIVE" and matching_action
                if not previous_relevant and not current_relevant:
                    reason="NO_RECORDED_ACTION";post_status="NOT_APPLICABLE"
                    message="이 제약에 연결된 행동이 활성 조건 아래의 이전·현재 기록에 없습니다. 기록이 맞다면 B8을 위해 수정할 항목은 없습니다. 금지·의무 위반은 B6에서 별도로 검사합니다."
                elif d.get("postcondition_window")!="NEXT_OBSERVATION":
                    reason="TIMING_REQUIRED";post_status="NOT_CHECKED"
                    message="기록 행동 뒤의 기대 결과를 언제 확인할지 정하지 않았습니다. 바로 다음 영상에서 확인할 결과라면 ‘기대 결과 확인 시점’을 ‘바로 다음 시점’으로 지정하세요."
                elif previous_relevant and previous_permitted:
                    reason="READY";post_status="CHECKED"
                    message="이전 기록 행동 뒤의 기대 결과를 현재 관찰 사실과 대조합니다."
                elif current_relevant:
                    reason="NEXT_SCENE_PENDING";post_status="NOT_CHECKED"
                    message="현재 기록 행동 뒤의 결과이므로 바로 다음 시점에서 검사합니다. 현재 장면의 확인 상태를 바꿀 필요는 없습니다. 다음 시점의 CoC·제약 관찰을 작성·검토한 뒤 검증하세요."
                else:
                    reason="PERMISSION_UNCONFIRMED";post_status="NOT_CHECKED"
                    message="이전 행동에 대한 허용 조건이 확인되지 않아 기대 결과 검사를 보류했습니다. 이전 시점의 시작·해제·행동 선행 조건에 대한 확인 항목부터 해결하세요."
                postcondition_checks.append({"condition_id":cid,"reason":reason,"status":post_status,"message":message,"sources":[deepcopy(ds)],"previous_actions":deepcopy(previous_actions),"current_actions":deepcopy(actions)})
            if previous_moment and prior=="ACTIVE" and d["expected_postconditions"] and d.get("postcondition_window")=="NEXT_OBSERVATION":
                matched=any(a["code"] in d["actions"] and a["subject_ref"]==d["subject_ref"] and a["action_target_ref"]==d["action_target_ref"] and a["movement_ref"]==d["movement_ref"] for a in previous_actions)
                prior_detail=previous_details.get(cid,{})
                permitted=d["effect"]!="ALLOW" or (prior_detail.get("permission_confirmed") and prior_detail.get("precondition_guard")=="TRUE")
                if matched and permitted:
                    for i,g in enumerate(d["expected_postconditions"]):
                        truth=guard_truth(g,facts);srcs=[ds]+fact_sources.get(atom_key(g["atom"]),[])
                        if truth in ("TRUE","FALSE"):
                            formula=builder.atom(atom_key(g["atom"]),srcs)
                            if g["expected_truth"]=="FALSE":formula=neg(formula)
                            builder.query("post_"+cid+"_"+str(i),formula,srcs)
                        else:finding("POSTCONDITION_UNKNOWN","바로 다음 장면의 기대 결과를 확인할 수 없습니다.",srcs)
        for a,src in zip(actions,action_sources):
            if a["code"]=="ENTER" and entity_kinds.get(a["action_target_ref"]) not in ("ZONE","LANE"):finding("UNSUPPORTED_ACTION_TARGET","관찰한 진입 행동의 대상 종류를 확인해야 합니다.",[src])
            if a["code"] in ("ENTER","START") and not any(a["code"] in r["definition"]["actions"] and a["action_target_ref"]==r["definition"]["action_target_ref"] and a["movement_ref"]==r["definition"]["movement_ref"] for r in ledger.values()):
                finding("ACTION_COVERAGE_MISSING","기록된 진입/출발의 구체 대상에 대응하는 제약 후보가 없습니다.",[src])
            action_var=builder.declare(symbol("action_",tuple(a.get(k) for k in ("code","subject_ref","action_target_ref","movement_ref"))),[src])
            stopped_key=("STOPPED","ego",None)
            if a["code"]=="HOLD" and facts.get(stopped_key) in ("TRUE","FALSE"):
                builder.clause(symbol("hold_means_stopped_",a),binary("implies",action_var,builder.atom(stopped_key)),[src]+fact_sources.get(stopped_key,[]))
            grounded_action=bool(set(a["evidence_refs"]) & current_evidence)
            if a["code"]=="ENTER":grounded_action=grounded_action and _supports_evidence(("RECORDED_ENTER","ego",a["action_target_ref"]),a["evidence_refs"],current_evidence)
            if not grounded_action:finding("EVIDENCE_MISSING","기록 행동의 현재 근거가 없습니다. 진입은 현재 영상 확인이 필요합니다.",[src])
        observed_names={symbol("action_",key) for key in all_action_keys}
        recorded_terms=[binary("eq",var(name),literal(name in observed_names)) for name in sorted(builder.names) if name.startswith("action_") and (name in observed_names or coc.get("action_observation_complete",False))]
        recorded=conjunction(*recorded_terms) if recorded_terms else literal(True)
        builder.query("base_consistency",literal(True),rule_sources)
        builder.query("recorded_action",recorded,rule_sources+action_sources)
        diagnostic=deepcopy(builder.core);diagnostic["model_id"]+="_conditions";diagnostic["clauses"]=[c for c in diagnostic["clauses"] if c["kind"]!="INVARIANT"];diagnostic["queries"]=[]
        for cid,formulas,srcs in checks:
            builder.refs(srcs);diagnostic["queries"].append({"id":"condition_"+cid,"formula":conjunction(recorded,*formulas),"expected":"SAT","classification":"CONSISTENCY","source_refs":builder.refs(srcs),"description":"Recorded action against "+cid})
        if not diagnostic["queries"]:
            diagnostic["queries"]=[{"id":"conditions_empty","formula":literal(True),"expected":"SAT","classification":"CONSISTENCY","source_refs":["profile"],"description":"No supported condition"}]
        diagnostic["source_refs"]=deepcopy(builder.core["source_refs"])
        for core in (builder.core,diagnostic,relation_core):
            key=_semantic_key(core)
            if key not in validated:parse_core_model(core);validated.add(key)
        row={"moment_id":m["id"],"ordinal":m["ordinal"],"t0_us":m["t0_us"],"status":status(codes),"codes":sorted(codes),"point_codes":[],"review_items":review,"notes":notes,"ledger":{cid:r["state"] for cid,r in ledger.items()},"states":states,"constraints":[deepcopy(r["definition"]) for r in ledger.values()],"explanation":coc.get("explanation",""),"observed_actions":deepcopy(actions),"core":builder.core,"condition_core":diagnostic,"relation_core":relation_core,"source_map":builder.source_map,"source_status":"REVIEW_REQUIRED" if source_review or not catalog_sources else "GROUNDED","source_review_items":source_review,"omitted_source_ids":[]}
        row["property_input"]={"moment":{k:deepcopy(m.get(k)) for k in ("id","ordinal","t0_us","coc","constraints","vehicle_state")},"entity_kinds":entity_kinds,"facts":[{"key":list(key),"truth":truth} for key,truth in facts.items()]}
        row["property_input"]["inherited_entities"]=deepcopy(inherited_entities(ledger))
        row["postcondition_checks"]=postcondition_checks
        scenes.append(row)
        if len(scenes)>1:pairs.append({"from_ordinal":scenes[-2]["ordinal"],"to_ordinal":m["ordinal"],"carried_ids":carried,"status":row["status"],"codes":row["codes"]})
        previous_entities=deepcopy(coc.get("entities",[])) if structured else []
        previous_actions=deepcopy(actions);previous_moment=m;previous_details=deepcopy(states)
    return {"version":VERSION,"continuation_summary":{"ledger":deepcopy(ledger),"previous_entities":previous_entities,"previous_actions":previous_actions,"previous_moment":{k:previous_moment[k] for k in ("id","ordinal","t0_us")},"previous_details":previous_details},"status":status([c for row in scenes for c in row["codes"]]),"source_status":"REVIEW_REQUIRED" if any(r["source_status"]=="REVIEW_REQUIRED" for r in scenes) else "GROUNDED","scenes":scenes,"pairs":pairs,"pending":[{"condition_id":cid,"state":r["state"]} for cid,r in ledger.items() if r["state"]!="RELEASED"],"scene_truth_certified":False,"rule_completeness_certified":False,"training_eligible":False}


def verify_grounded_compiled(compiled):
    # Compiled Core/source maps belong to the separate EBLC artifact. Copy only
    # review results; duplicating those models here exceeds the CPU child's
    # memory cap when its complete result is serialized.
    result={k:deepcopy(v) for k,v in compiled.items() if k!="scenes"};result["scenes"]=[];cache={}
    def solve(core):
        key=_semantic_key(core)
        if key not in cache:cache[key]=_bounded_solve(core)
        solved=deepcopy(cache[key]);solved["model_id"]=core["model_id"]
        clauses={c["id"]:c for c in core["clauses"]};queries={q["id"]:q for q in core["queries"]}
        for q in solved["results"]:
            q["source_refs"]=sorted(set(queries[q["query_id"]]["source_refs"])|{ref for cid in q["unsat_clause_ids"] for ref in clauses[cid]["source_refs"]})
        return solved
    model_fields={"core","condition_core","relation_core","source_map","property_input"}
    for stored in compiled["scenes"]:
        row={k:deepcopy(v) for k,v in stored.items() if k not in model_fields}
        smt=solve(stored["core"]);conditions=solve(stored["condition_core"]);relations=solve(stored["relation_core"])
        by_id={r["query_id"]:r for r in smt["results"]};codes=set(row["codes"])
        def add(code,message,queries):
            codes.add(code);refs={ref for q in queries for ref in q["source_refs"]}
            row["review_items"].append({"code":code,"message":message,"sources":[deepcopy(stored["source_map"][ref]) for ref in sorted(refs) if ref in stored["source_map"]]})
        relation_bad=[q for q in relations["results"] if q["status"]=="UNSAT"]
        if relation_bad:add("RELATION_CONTRADICTION","방향 있는 관계/현재 사실이 서로 모순됩니다.",relation_bad)
        elif by_id["base_consistency"]["status"]=="UNSAT":add("RULE_CONTRADICTION","활성 제약들의 요구/금지가 충돌합니다.",[by_id["base_consistency"]])
        elif by_id["recorded_action"]["status"]=="UNSAT":
            bad=[q for q in conditions["results"] if q["status"]=="UNSAT"]
            add("ACTION_CONTRADICTION","구체 대상에 기록된 행동이 활성 제약과 충돌합니다.",bad or [by_id["recorded_action"]])
        for q in smt["results"]:
            if q["query_id"].startswith("post_") and q["status"]=="UNSAT" and by_id["base_consistency"]["status"]=="SAT":add("POSTCONDITION_CONTRADICTION","이전 행동의 기대 결과가 바로 다음 장면의 사실과 충돌합니다.",[q])
        unknown=[q for table in (smt,conditions,relations) for q in table["results"] if q["status"] not in ("SAT","UNSAT")]
        if unknown:add("SOLVER_UNKNOWN","제한된 시간 안에 논리 검증이 확정되지 않았습니다.",unknown)
        row["codes"]=sorted(codes);row["status"]=status(codes)
        row["verification"]={"core_model_id":stored["core"]["model_id"],"condition_model_id":stored["condition_core"]["model_id"],"relation_model_id":stored["relation_core"]["model_id"],"smt":smt,"condition_checks":conditions,"relation_checks":relations,"observed_offsets":[0],"unobserved_offsets":[],"note":"Core/source maps are in the compiled EBLC artifact. Horizon=2; bounded prior/current summary, no future observations asserted."}
        from .studio_properties import evaluate
        row["properties"]=evaluate(stored,row)
        for pid,code in (("A1","JUSTIFICATION_CONTRADICTION"),("A4","CAN_ACTION_CONTRADICTION")):
            prop=next(p for p in row["properties"]["results"] if p["property_id"]==pid)
            if prop["status"]=="FAIL":
                codes.add(code);row["review_items"].append({"code":code,"message":prop["message"],"sources":prop["sources"]})
        coverage=next(p for p in row["properties"]["results"] if p["property_id"]=="A2")
        if any(c.get("missing") for c in coverage["checks"]):
            codes.add("REQUIRED_CONDITION_MISSING");row["review_items"].append({"code":"REQUIRED_CONDITION_MISSING","message":"진입·출발에 필요한 경로 비움 또는 신호 적용성 조건이 빠졌습니다.","sources":coverage["sources"]})
        row["codes"]=sorted(codes);row["status"]=status(codes)
        result["scenes"].append(row)
    for pair,row in zip(result["pairs"],result["scenes"][1:]):pair.update(status=row["status"],codes=row["codes"])
    result["status"]=status([c for row in result["scenes"] for c in row["codes"]])
    return result


def render_grounded_constraints(definitions, entity_labels=None, *, detailed=False, origin_labels=None):
    action_names={"START":"출발","STOP":"정지 동작","CONTINUE":"주행 지속","ENTER":"영역 진입","HOLD":"정지 유지"}
    labels={**(entity_labels or {}),"ego":"자차"}
    def ref(identity):return labels.get(identity) or "연결이 확인되지 않은 대상"
    def confirmed(fact):
        last=ord(fact[-1]);particle='이' if 0xac00<=last<=0xd7a3 and (last-0xac00)%28 else '가'
        return fact+particle+' 확인되면'
    def guards(gs, compact=False, aliases=None):
        statements=[]
        for g in gs:
            a=g['atom'];subject='‘'+(aliases or {}).get(a['subject_ref'],ref(a['subject_ref']))+'’';target='‘'+(aliases or {}).get(a['object_ref'],ref(a['object_ref']))+'’'
            phrases={"SIGNAL_RED":f"{subject}: 적색 신호임","SIGNAL_GREEN":f"{subject}: 녹색 신호임",
                     "PATH_CLEAR":f"{subject}: 진행 경로가 비어 있음","ZONE_CLOSED":f"{subject}: 통행이 막혀 있음",
                     "STOPPED":f"{subject}: 정지해 있음","VISIBILITY_INSUFFICIENT":f"{subject}: 시야가 부족함"+(f" · 영향 대상: {target}" if a['object_ref'] else ''),
                     "SURFACE_RISK":f"{subject}: 노면 위험이 있음"+(f" · 영향 대상: {target}" if a['object_ref'] else ''),"LEFT_OF":f"{subject}: {target}의 왼쪽에 있음",
                     "RIGHT_OF":f"{subject}: {target}의 오른쪽에 있음","AHEAD_OF":f"{subject}: {target}보다 앞에 있음",
                     "BEHIND_OF":f"{subject}: {target}보다 뒤에 있음","IN":f"{subject}: {target} 안에 있음",
                     "OCCUPIES":f"{subject}: {target}을 점유함","ADJACENT_TO":f"{subject}: {target}에 인접함",
                     "BOUNDARY_OF":f"{subject}: {target}의 경계를 이룸","APPLIES_TO":f"{subject}: {target}에 적용됨",
                     "PATH_CONFLICT":f"{subject}: {target}의 진행 경로와 겹침",
                     "PASSAGE_COMPLETE":f"{subject}: {target}을 완전히 지나침" if a['object_ref'] else f"{subject}: 통과가 완료됨"}
            fact=phrases.get(a['predicate'],'지원하지 않는 관계 · 정의 확인 필요')
            if compact:
                fact={"ZONE_CLOSED":f"{subject}의 통행 차단", "PASSAGE_COMPLETE":f"{subject}의 {target} 통과 완료" if a['object_ref'] else f"{subject}의 통과 완료"}.get(a['predicate'],fact)
                statements.append(fact if g['expected_truth']=='TRUE' else '「'+fact+'」이 아니라는 사실')
                continue
            statements.append('「'+fact+'」'+('이 성립함' if g['expected_truth']=='TRUE' else '이 성립하지 않음'))
        return '; '.join(statements)
    paragraphs=[]
    for i,d in enumerate(definitions,1):
        actions=', '.join(action_names[a] for a in d['actions'])
        if not detailed:
            target_ref=d['action_target_ref'];alias='해당 영역' if 'ENTER' in d['actions'] else '해당 대상'
            aliases={target_ref:alias} if target_ref and target_ref!=d['subject_ref'] else {}
            heading=f"{i}. {ref(target_ref)}" if aliases and labels.get(target_ref) else f"{i}. {d['description']}"+(' · 대상 연결 확인 필요' if aliases else '')
            if (origin_labels or {}).get(d['condition_id']):heading+=' · '+origin_labels[d['condition_id']]
            target='‘'+alias+'’ ' if aliases and d['actions']==['ENTER'] else '‘'+alias+'’에 대한 ' if aliases else ''
            movement='‘'+ref(d['movement_ref'])+'’ 경로에서의 ' if d['movement_ref'] and d['movement_ref']!=d['subject_ref'] else ''
            effect={'FORBID':'금지한다','REQUIRE':'요구한다','ALLOW':'다른 적용 제약과 충돌하지 않을 때만 허용한다'}[d['effect']]
            short_actions='진입' if d['actions']==['ENTER'] else actions
            action=f"{ref(d['subject_ref'])}의 {movement}{target}{short_actions} 행동을 {effect}."
            if d['activation_all_of']:
                start=guards(d['activation_all_of'],True,aliases)
                lines=[heading,('다음 조건이 모두 확인되면: '+start+'. ' if len(d['activation_all_of'])>1 else confirmed(start)+', ')+action]
            else:lines=[heading,'시작 조건이 정의되지 않아 적용 여부를 확인해야 한다. '+action]
            if d['release_any_of']:
                release=guards(d['release_any_of'],True,aliases)
                lines.append(('다음 중 하나라도 확인되면: '+release+'. ' if len(d['release_any_of'])>1 else confirmed(release)+', ')+'이 제약을 해제하며 그 전까지 유지한다.')
            else:lines.append('해제 조건이 정의되지 않았다. 확인 없이 이 제약을 해제하지 않는다.')
            if d['preconditions']:lines.append('행동 전에는 다음 조건도 모두 확인해야 한다: '+guards(d['preconditions'],True,aliases)+'.')
            paragraphs.append('\n'.join(lines));continue
        target=' · 대상: ‘'+ref(d['action_target_ref'])+'’' if d['action_target_ref'] else ''
        movement=' · 진행 경로: ‘'+ref(d['movement_ref'])+'’' if d['movement_ref'] and d['movement_ref']!=d['subject_ref'] else ''
        lines=[f"{i}. {d['description']}",f"행동 제약: {ref(d['subject_ref'])}의 {actions}{target}{movement} — "+{'FORBID':'금지한다.','REQUIRE':'수행해야 한다.','ALLOW':'다른 적용 제약과 충돌하지 않는 경우에만 허용한다.'}[d['effect']]]
        if (origin_labels or {}).get(d['condition_id']):lines[0]+=' · '+origin_labels[d['condition_id']]
        lines.append('시작: 다음 사실이 모두 확인되면 적용한다. '+guards(d['activation_all_of']) if d['activation_all_of'] else '시작: 조건이 정의되지 않아 적용 여부를 확정할 수 없다.')
        lines.append('유지: 해제 조건이 확인될 때까지 유지한다.')
        lines.append('해제: 다음 사실 중 하나 이상이 확인되면 해제한다. '+guards(d['release_any_of']) if d['release_any_of'] else '해제: 조건이 정의되지 않아 자동으로 해제하지 않는다.')
        if d['preconditions']:lines.append('행동 전 확인: 다음 사실이 모두 확인되어야 한다. '+guards(d['preconditions']))
        if d['expected_postconditions']:
            lines.append('행동 뒤 기대 결과: 이 제약에 연결된 행동을 실제 수행한 경우에 기대하는 사실이다. '+guards(d['expected_postconditions']))
            lines.append('기대 결과 확인 시점: '+('행동을 기록한 바로 다음 장면.' if d.get('postcondition_window')=='NEXT_OBSERVATION' else '아직 정하지 않음.'))
        paragraphs.append('\n'.join(lines))
    return '\n\n'.join(paragraphs)


def render_grounded_verified(compiled, verification):
    names={"PASS":"입력한 조건 안에서 일치","REVIEW_REQUIRED":"추가 확인 필요","CONTRADICTION":"모순 발견"};samples=[]
    ordinals={s['moment_id']:s['ordinal'] for s in compiled['scenes']}
    for scene,checked in zip(compiled["scenes"],verification["scenes"]):
        if scene["moment_id"]!=checked["moment_id"]:raise ValueError("Compiled/verified scene identity mismatch")
        entities=scene.get('property_input',{}).get('moment',{}).get('coc') or {}
        current_labels={e['entity_id']:e['description'] for e in entities.get('entities',[])}
        # Names belong to retained constraint targets, not incidental local IDs
        # reused by the preceding scene (including unreviewed scene drafts).
        labels={**current_labels,**{e['entity_id']:e['description'] for e in scene.get('property_input',{}).get('inherited_entities',[])}}
        origins={}
        for src in scene.get('source_map',{}).values():
            if src.get('component')!='sequence_constraints' or not src.get('path','').startswith('/new_definitions/'):continue
            if src.get('moment_id')==scene['moment_id'] or not isinstance(src.get('value'),dict):continue
            d=src['value']
            if d not in scene['constraints']:continue
            ordinal=ordinals.get(src['moment_id'])
            origins[d['condition_id']]=f'시점 {ordinal+1}에서 이어받은 제약' if ordinal is not None else '이전 시점에서 이어받은 제약'
        constraint_text=render_grounded_constraints(scene["constraints"],labels,origin_labels=origins) or "생성된 제약이 없습니다."
        constraint_details=render_grounded_constraints(scene["constraints"],labels,detailed=True,origin_labels=origins)
        text='CoC\n'+(scene['explanation'] or '작성된 CoC 설명이 없습니다.')+'\n\n제약 사항\n'+constraint_text
        properties=checked.get("properties",{});counts=properties.get("counts",{})
        scope=f"12개 속성: 일치 {counts.get('PASS',0)}, 위반 {counts.get('FAIL',0)}, 확인 필요 {counts.get('UNKNOWN',0)}, 미검사 {counts.get('NOT_CHECKED',0)}, 해당 없음 {counts.get('NOT_APPLICABLE',0)}. 이전·현재 두 장면 범위이며 미검사는 통과가 아닙니다.\n" if properties else ""
        samples.append({"moment_id":scene["moment_id"],"ordinal":scene["ordinal"],"status":checked["status"],"properties_status":properties.get("status"),"text":text,"combined":text,"constraint_details":constraint_details,"verification_text":f"검증 상태: {names[checked['status']]}\n"+scope.rstrip()})
    return {"samples":samples,"training_eligible":False,"status":verification["status"],"source_status":verification["source_status"]}
