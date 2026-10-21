"""Recorded-action, qualitative sequence profile using the reusable EBLC Core.

VLM observations remain claims. Ledger continuity and SMT satisfiability do not
certify perception, rule completeness, motor commands or collision avoidance.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import guard_synth_eblc.core_ir as core_ir
import guard_synth_eblc.smt_compiler as smt_compiler
import re

from guard_synth_eblc.schema_validation import validate
from guard_synth_eblc.action_contract import var, literal, binary, conjunction, neg
from guard_synth_eblc.core_ir import parse_core_model
from guard_synth_eblc.smt_compiler import compile_core_model, check_queries

VERSION = "studio-sequential-coc-v0.2-grounded"
ACTIONS = {"START": "출발", "STOP": "정지 행동", "CONTINUE": "주행 지속", "ENTER": "영역 진입", "HOLD": "정지 유지"}
IDENTITY_FIELDS = ("scope_id", "description", "actions", "effect", "activation", "hold", "release", "source_refs")


def tool_signature():
    from . import studio_grounded_sequence as grounded
    from . import studio_properties as properties
    from . import studio_relations as relations
    files=(Path(__file__),Path(grounded.__file__),Path(properties.__file__),Path(relations.__file__),Path(core_ir.__file__),Path(smt_compiler.__file__))
    return hashlib.sha256(VERSION.encode()+b"".join(p.read_bytes() for p in files)).hexdigest()


def closed(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def legacy_schema(task):
    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    actions = {"type": "array", "items": {"type": "string", "enum": list(ACTIONS)}}
    if task == "SEQ_COC":
        return closed({"observations": string, "observed_actions": actions, "explanation": string,
                       "unknowns": string, "evidence_refs": strings})
    if task != "SEQ_CONSTRAINTS":
        raise ValueError("Unknown sequence generation task")
    properties = {k: string for k in ("condition_id", "scope_id", "description", "activation", "hold", "release", "evidence_note")}
    properties.update(actions=actions, effect={"type": "string", "enum": ["FORBID", "REQUIRE"]},
                      truth={"type": "string", "enum": ["TRUE", "FALSE", "UNKNOWN", "CONFLICT"]},
                      scope_state={"type": "string", "enum": ["IN_SCOPE", "ENDED", "UNKNOWN"]},
                      source_refs=strings, evidence_refs=strings)
    from .studio_grounded_sequence import CLASSES
    item=closed(properties)
    item["properties"]["condition_class"]={"type":["string","null"],"enum":CLASSES+[None]}
    return closed({"constraints": {"type": "array", "items": item}})


def candidate_schema(task, context=None):
    from .studio_grounded_sequence import grounded_schema
    return grounded_schema(task, context)


def validate_candidate(task, data, frame_ids, source_ids, context=None):
    if "entities" in data or "new_definitions" in data:
        from .studio_grounded_sequence import validate_grounded
        return validate_grounded(task, data, frame_ids, source_ids, context)
    validate(data, legacy_schema(task))
    items = data["constraints"] if task == "SEQ_CONSTRAINTS" else [data]
    if len(items) > 16:
        raise ValueError("At most 16 conditions per moment")
    seen = set()
    for item in items:
        if not set(item["evidence_refs"]).issubset(frame_ids):
            raise ValueError("Evidence must refer to supplied causal frame IDs")
        actions=item["actions"] if task=="SEQ_CONSTRAINTS" else item["observed_actions"]
        if len(actions)!=len(set(actions)):
            raise ValueError("Actions must be unique")
        if task == "SEQ_CONSTRAINTS":
            cid = item["condition_id"]
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", cid) or cid in seen:
                raise ValueError("Invalid or duplicate stable condition ID")
            seen.add(cid)
            if not item["scope_id"].strip() or not item["actions"] or not all(item[k].strip() for k in ("description", "activation", "hold", "release")):
                raise ValueError("Scope, target actions and lifecycle descriptions required")
            if not set(item["source_refs"]).issubset(source_ids):
                raise ValueError("Source ID was not supplied")
    return deepcopy(data)


def render_constraints(items):
    return "\n".join(f"{c['description']}인 경우 {', '.join(ACTIONS[a] for a in c['actions'])}을 "
                     f"{'허용하지 않는다' if c['effect']=='FORBID' else '요구한다'}. "
                     f"발동: {c['activation']}. 유지: {c['hold']}. 해제: {c['release']}." for c in items)


def advance(ledger, items):
    codes = set()
    for record in ledger.values():
        record.update(prior_state=record["state"], on=False, clear=False, observed=False)
    for c in items:
        cid = c["condition_id"]
        old = ledger.get(cid)
        if old and any((set(old["definition"][k]) != set(c[k])) if k in ("actions","source_refs") else (old["definition"][k] != c[k]) for k in IDENTITY_FIELDS):
            codes.add("IDENTITY_CONFLICT")
            continue
        if old is None:
            if len(ledger) >= 64:
                raise ValueError("At most 64 stable conditions per event")
            old = ledger[cid] = {"definition": deepcopy(c), "state": "UNKNOWN", "prior_state": "UNKNOWN", "scope_ended":False}
        valid = bool(c["evidence_refs"] and c["evidence_note"].strip())
        on = valid and c["truth"] == "TRUE" and c["scope_state"] == "IN_SCOPE"
        clear = valid and (c["scope_state"] == "ENDED" or (c["truth"] == "FALSE" and c["scope_state"] == "IN_SCOPE"))
        old.update(on=on, clear=clear, observed=True)
        if c["truth"] == "CONFLICT":
            codes.add("OBSERVATION_CONFLICT")
            # Conflicting observations cannot release even with a scope-end claim.
            on = clear = False
            old.update(on=False, clear=False)
        if on:
            old["state"] = "ACTIVE"
            old["scope_ended"] = False
        elif clear:
            old["state"] = "RELEASED"
            old["scope_ended"] = c["scope_state"] == "ENDED"
        else:
            codes.add("EVIDENCE_MISSING")
    if any(not r["observed"] and not r["scope_ended"] for r in ledger.values()):
        codes.add("EVIDENCE_MISSING")
    return codes


def build_core(ledger, observed_actions, ordinal):
    refs = sorted({s for r in ledger.values() for s in r["definition"]["source_refs"]}) or ["candidate_claim"]
    core = {"grammar_version": "eblc-core-v0.1", "model_id": "sequence_"+str(ordinal), "horizon": 2,
            "source_refs": refs, "claim_scope": "CONDITIONAL_STATEMENT_CONSISTENCY_NOT_SCENE_TRUTH",
            "declarations": [], "clauses": [], "queries": []}
    def declare(name):
        core["declarations"].append({"name": name, "sort": "BOOL", "time_varying": False,
            "enum_name": None, "enum_values": [], "unit": None, "frame": None, "source_refs": refs})
    def clause(cid, formula, kind="INVARIANT"):
        core["clauses"].append({"id": cid, "kind": kind, "enforcement": "INITIAL", "formula": formula,
                               "source_refs": refs, "description": cid})
    for action in ACTIONS:
        declare("action_"+action.lower())
    clause("conditional_profile", literal(True), "ASSUMPTION")
    for cid, r in ledger.items():
        prev, active = cid+"_previous", cid+"_active"
        declare(prev); declare(active)
        if r["prior_state"] != "UNKNOWN":
            clause(cid+"_carry", binary("eq",var(prev),literal(r["prior_state"]=="ACTIVE")),"ASSUMPTION")
        clause(cid+"_transition", binary("eq",var(active),{"op":"ite", "condition":literal(r["on"]),
            "then":literal(True), "else":{"op":"ite", "condition":literal(r["clear"]),
            "then":literal(False), "else":var(prev)}}),"LIFECYCLE")
        for a in r["definition"]["actions"]:
            outcome=var("action_"+a.lower())
            if r["definition"]["effect"]=="FORBID":
                outcome=neg(outcome)
            clause(cid+"_"+a.lower(),binary("implies",var(active),outcome))
    observed = conjunction(*(binary("eq",var("action_"+a.lower()),literal(a in observed_actions)) for a in ACTIONS))
    for qid, formula in [("base_consistency",literal(True)),("recorded_action",observed)]:
        core["queries"].append({"id":qid,"formula":formula,"expected":"SAT","classification":"CONSISTENCY",
                                "source_refs":refs,"description":qid})
    diagnostic=deepcopy(core)
    diagnostic["model_id"]+="_conditions"
    diagnostic["clauses"]=[c for c in core["clauses"] if c["kind"]!="INVARIANT"]
    diagnostic["queries"]=[]
    for cid,r in ledger.items():
        formulas=[c["formula"] for c in core["clauses"] if c["id"] in {cid+"_"+a.lower() for a in r["definition"]["actions"]}]
        diagnostic["queries"].append({"id":"condition_"+cid,"formula":conjunction(observed,*formulas),
            "expected":"SAT","classification":"CONSISTENCY","source_refs":refs,"description":"Isolate "+cid+" against recorded action"})
    parse_core_model(core)
    if ledger: parse_core_model(diagnostic)
    return {"core":core,"condition_core":diagnostic if ledger else None}


def check_core(models, observed_actions):
    core,diagnostic=models["core"],models["condition_core"]
    result=check_queries(compile_core_model(parse_core_model(core)))
    statuses={q["query_id"]:q["status"] for q in result["results"]}
    codes=set()
    if statuses["base_consistency"]=="UNSAT": codes.add("RULE_CONTRADICTION")
    elif observed_actions and statuses["recorded_action"]=="UNSAT": codes.add("ACTION_CONTRADICTION")
    if any(v not in ("SAT","UNSAT") for v in statuses.values()): codes.add("SOLVER_UNKNOWN")
    condition_checks=check_queries(compile_core_model(parse_core_model(diagnostic))) if diagnostic else {"results":[]}
    for item in condition_checks["results"]:
        item.pop("smt2",None);item.pop("witness",None)
    return codes,{"core":core,"smt":result,"condition_core":diagnostic,"condition_checks":condition_checks,
                  "observed_offsets":[0],"unobserved_offsets":[],
                  "note":"Core minimum horizon=2; all declarations constant, no future scene asserted."}


def smt_check(ledger, observed_actions, ordinal):
    return check_core(build_core(ledger,observed_actions,ordinal),observed_actions)


def _compile_legacy_sequence(moments, catalog):
    if not 1 <= len(moments) <= 200:
        raise ValueError("Verify 1–200 ordered moments")
    if [m["ordinal"] for m in moments] != sorted(set(m["ordinal"] for m in moments)) or any(b["t0_us"] <= a["t0_us"] for a,b in zip(moments,moments[1:])):
        raise ValueError("Moments must be unique and chronological")
    sources = {s["id"]:s for s in catalog["sources"]}
    ledger, scenes, pairs = {}, [], []
    solver_cache={}
    def solve(states,actions,ordinal):
        key=repr((sorted(actions),[(cid,r["prior_state"],r["on"],r["clear"],r["definition"]["effect"],sorted(r["definition"]["actions"]),sorted(r["definition"]["source_refs"])) for cid,r in sorted(states.items())]))
        if key not in solver_cache:
            solver_cache[key]=build_core(states,actions,ordinal)
        return solver_cache[key]
    for m in moments:
        coc, items = m["coc"],m["constraints"]["constraints"]
        validate_candidate("SEQ_COC",coc,set(m["frame_ids"]),set(sources))
        validate_candidate("SEQ_CONSTRAINTS",{"constraints":items},set(m["frame_ids"]),set(sources) | {s for c in items for s in c["source_refs"]})
        carried=sorted(k for k,r in ledger.items() if r["state"]!="RELEASED")
        codes=advance(ledger,items)
        if not items or not m["reviewed"] or not coc["observed_actions"] or not coc["evidence_refs"]:
            codes.add("REVIEW_REQUIRED")
        if not sources:
            codes.add("CATALOG_MISSING")
        for r in ledger.values():
            sr=r["definition"]["source_refs"]
            if not sr or any(s not in sources or not sources[s]["reviewed"] for s in sr): codes.add("UNGROUNDED")
        covered={(s,a) for r in ledger.values() if not r["scope_ended"] or r["observed"] for s in r["definition"]["source_refs"] for a in r["definition"]["actions"]}
        omitted=[s["id"] for s in sources.values() if any((s["id"],a) not in covered for a in set(s["expected_actions"]) & set(coc["observed_actions"]))]
        if omitted: codes.add("POSSIBLE_OMISSION")
        if m.get("observation_gap"): codes.add("OBSERVATION_GAP")
        if any(r["state"]=="UNKNOWN" for r in ledger.values()): codes.add("EVIDENCE_MISSING")
        models = solve(ledger,coc["observed_actions"],m["ordinal"])
        point={};point_codes=advance(point,items)
        point_models=solve(point,coc["observed_actions"],m["ordinal"])
        contradiction=bool(codes & {"RULE_CONTRADICTION","ACTION_CONTRADICTION","IDENTITY_CONFLICT","OBSERVATION_CONFLICT"})
        row={"moment_id":m["id"],"ordinal":m["ordinal"],"t0_us":m["t0_us"],"codes":sorted(codes),
             "point_codes":sorted(point_codes),"status":"CONTRADICTION" if contradiction else "REVIEW_REQUIRED" if codes else "PASS",
             "omitted_source_ids":omitted,"ledger":{k:r["state"] for k,r in ledger.items()},
             **models,"point_models":point_models,"observed_actions":coc["observed_actions"],
             "constraints":[deepcopy(r["definition"]) for r in ledger.values() if not r["scope_ended"] or r["observed"]],"explanation":coc["explanation"]}
        scenes.append(row)
        if len(scenes)>1:
            pairs.append({"from_ordinal":scenes[-2]["ordinal"],"to_ordinal":m["ordinal"],"carried_ids":carried,
                          "status":row["status"],"codes":row["codes"]})
    statuses={r["status"] for r in scenes}
    return {"version":VERSION,"status":"CONTRADICTION" if "CONTRADICTION" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS",
            "scenes":scenes,"pairs":pairs,"pending":[{"condition_id":k,"state":r["state"]} for k,r in ledger.items() if r["state"]!="RELEASED"],
            "scene_truth_certified":False,"rule_completeness_certified":False,"training_eligible":False}



def _verify_legacy_compiled(compiled):
    scenes=[];cache={}
    def solve(models,actions):
        # Model IDs are presentation labels; equal formulas share solver work.
        key=repr([{**m,"model_id":"cached"} if m else None for m in (models["core"],models["condition_core"])])+repr(sorted(actions))
        if key not in cache: cache[key]=check_core(models,actions)
        return cache[key]
    for stored in compiled["scenes"]:
        row=deepcopy(stored)
        actions=row.pop("observed_actions")
        models={k:row.pop(k) for k in ("core","condition_core")}
        point=row.pop("point_models")
        row.pop("constraints");row.pop("explanation")
        smt_codes,verification=solve(models,actions)
        row["codes"]=sorted(set(row["codes"])|smt_codes)
        row["point_codes"]=sorted(set(row["point_codes"])|solve(point,actions)[0])
        row["verification"]=verification
        contradiction=bool(set(row["codes"]) & {"RULE_CONTRADICTION","ACTION_CONTRADICTION","IDENTITY_CONFLICT","OBSERVATION_CONFLICT"})
        row["status"]="CONTRADICTION" if contradiction else "REVIEW_REQUIRED" if row["codes"] else "PASS"
        scenes.append(row)
    result={**deepcopy(compiled),"scenes":scenes}
    for pair,row in zip(result["pairs"],scenes[1:]): pair.update(status=row["status"],codes=row["codes"])
    statuses={r["status"] for r in scenes}
    result["status"]="CONTRADICTION" if "CONTRADICTION" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS"
    return result


def verify_sequence(moments,catalog):
    return verify_compiled(compile_sequence(moments,catalog))


def _render_legacy_verified(compiled,verification):
    samples=[]
    names={"PASS":"입력한 조건 안에서 일치","REVIEW_REQUIRED":"추가 확인 필요","CONTRADICTION":"모순 발견"}
    for scene,checked in zip(compiled["scenes"],verification["scenes"]):
        assert scene["moment_id"]==checked["moment_id"]
        constraint_text=render_constraints(scene["constraints"]) or "생성된 제약이 없습니다."
        text='CoC\n'+(scene['explanation'] or '작성된 CoC 설명이 없습니다.')+'\n\n제약 사항\n'+constraint_text
        samples.append({"moment_id":scene["moment_id"],"ordinal":scene["ordinal"],"status":checked["status"],
                        "text":text,"combined":text,"verification_text":f"검증 상태: {names[checked['status']]}"})
    return {"samples":samples,"training_eligible":False,"status":verification["status"]}


def compile_sequence(moments, catalog):
    legacy = bool(moments) and all(isinstance(m.get("coc"), dict) and "entities" not in m["coc"] and isinstance(m.get("constraints"), dict) and "constraints" in m["constraints"] for m in moments)
    if legacy:
        return _compile_legacy_sequence(moments, catalog)
    from .studio_grounded_sequence import compile_grounded_sequence
    return compile_grounded_sequence(moments, catalog)


def verify_compiled(compiled):
    from .studio_grounded_sequence import VERSION as grounded_version, verify_grounded_compiled
    if compiled.get("version") in (grounded_version,"studio-grounded-sequential-coc-v0.2"):
        return verify_grounded_compiled(compiled)
    result=_verify_legacy_compiled(compiled)
    from .studio_properties import evaluate
    for stored,row in zip(compiled["scenes"],result["scenes"]):row["properties"]=evaluate(stored,row)
    return result


def render_verified(compiled, verification):
    from .studio_grounded_sequence import VERSION as grounded_version, render_grounded_verified
    if compiled.get("version") in (grounded_version,"studio-grounded-sequential-coc-v0.2"):
        return render_grounded_verified(compiled, verification)
    return _render_legacy_verified(compiled, verification)
