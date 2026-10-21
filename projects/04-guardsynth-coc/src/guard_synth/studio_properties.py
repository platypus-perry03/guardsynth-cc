"""Twelve bounded Studio properties; unknown evidence is never a negative fact.

The coverage checklist is a versioned research criterion, not a traffic-law
certificate. These queries consume only the current scene and prior summary.
"""
from copy import deepcopy
import math
import z3

VERSION = "studio-properties-v1"
PROFILE = {"id": "entry-path-review-v1", "reviewed": True,
           "can_max_age_us": 600000, "stationary_max_kmh": 0.5, "moving_min_kmh": 2.0,
           "solver_timeout_ms": 500, "horizon": 2}
PROPERTIES = [
    ("B1", "CONSISTENCY", "대상·관계 형식"), ("B2", "GROUNDING", "근거 시점·대상"),
    ("B3", "CONSISTENCY", "관찰·공간 관계"), ("B4", "CONSISTENCY", "조건 정의 동일성"),
    ("B5", "SAFETY", "조건 유지·해제"), ("B6", "SAFETY", "제약·기록 행동"),
    ("B7", "SAFETY", "행동 선행 조건"), ("B8", "SAFETY", "행동 후 기대 결과"),
    ("A1", "GROUNDING", "설명의 이유·근거"), ("A2", "COVERAGE", "필요 조건 누락"),
    ("A3", "SAFETY", "허용·금지 통합"), ("A4", "GROUNDING", "행동·CAN 측정"),
]
CODE_MAP = {
    "B1": {"UNSUPPORTED_ATOM", "UNBOUND_TARGET", "UNSUPPORTED_ACTION_TARGET", "ENTITY_IDENTITY_UNCERTAIN", "LEGACY_INPUT_GAP"},
    "B2": {"EVIDENCE_MISSING", "OBSERVATION_GAP"},
    "B3": {"OBSERVATION_CONFLICT", "RELATION_CONTRADICTION"},
    "B4": {"IDENTITY_CONFLICT"}, "B5": {"LIFECYCLE_CONFLICT", "PRIOR_CONTEXT_MISSING", "UNRESOLVED_PREVIOUS"},
    "B6": {"RULE_CONTRADICTION", "ACTION_CONTRADICTION"},
    "B7": {"PRECONDITION_CONTRADICTION", "PRECONDITION_UNKNOWN"},
    "B8": {"POSTCONDITION_CONTRADICTION", "POSTCONDITION_UNKNOWN"},
}


class Evidence:
    def __init__(self, records, kinds):
        self.solver = z3.Solver(); self.solver.set(timeout=PROFILE["solver_timeout_ms"])
        self.variables = {}; self.kinds = kinds
        for key, truth in records:
            term = self.atom(key)
            if truth in ("TRUE", "FALSE"): self.solver.add(term == (truth == "TRUE"))
            elif truth == "CONFLICT": self.solver.add(z3.BoolVal(False))

    def atom(self, key):
        from .studio_grounded_sequence import symbol
        key = tuple(key)
        if key not in self.variables:
            self.variables[key] = z3.Bool(symbol("property_", key))
            p, a, b = key
            if p == "ADJACENT_TO":
                self.solver.add(self.variables[key] == self.atom((p,b,a)))
            if p in ("LEFT_OF", "RIGHT_OF", "AHEAD_OF", "BEHIND_OF"):
                axis = "x" if p in ("LEFT_OF", "RIGHT_OF") else "y"
                left, right = z3.Int(symbol(axis, a)), z3.Int(symbol(axis, b))
                self.solver.add(self.variables[key] == (left < right if p in ("LEFT_OF", "BEHIND_OF") else left > right))
        return self.variables[key]

    def guards(self, guards, any_of=False):
        from .studio_grounded_sequence import atom_key, _supported_atom
        terms = []
        for g in guards:
            key = atom_key(g["atom"])
            # Unsupported predicates remain unconstrained; B1 explains the gap.
            term = self.atom(key if _supported_atom(key, self.kinds) else ("UNBOUND", repr(key), None))
            terms.append(term if g["expected_truth"] == "TRUE" else z3.Not(term))
        return (z3.Or if any_of else z3.And)(*terms)

    def query(self, formula):
        self.solver.push(); self.solver.add(formula); result = self.solver.check()
        witness = {str(k): str(self.solver.model().eval(v, model_completion=True)) for k, v in self.variables.items()} if result == z3.sat else {}
        reason = self.solver.reason_unknown() if result == z3.unknown else None
        self.solver.pop()
        return {"status": str(result).upper(), "witness": witness, "reason_unknown": reason}

    def support(self, formula):
        base = self.query(z3.BoolVal(True))
        if base["status"] != "SAT": return {"status": "UNKNOWN", "reason": "INPUT_CONFLICT" if base["status"] == "UNSAT" else "SOLVER_UNKNOWN", "base": base}
        positive, negative = self.query(formula), self.query(z3.Not(formula))
        state = "PASS" if negative["status"] == "UNSAT" else "FAIL" if positive["status"] == "UNSAT" else "UNKNOWN"
        return {"status": state, "positive": positive, "negative": negative}


def same_action(d, a):
    return a["code"] in d["actions"] and all(a.get(k) == d.get(k) for k in ("subject_ref", "action_target_ref", "movement_ref"))


def can_check(action, m):
    code = action["code"]
    if code not in ("HOLD", "CONTINUE", "START", "STOP"): return {"status": "NOT_APPLICABLE", "message": "진입 여부는 CAN 속도로 확인하지 않습니다."}
    records = (m.get("vehicle_state") or {}).get("frames", [])
    aligned = [r for r in records if r["frame_timestamp_us"] == m["t0_us"]]
    if not aligned or not aligned[-1].get("sample"): return {"status": "NOT_CHECKED", "message": "현재 영상과 연결된 CAN 측정이 없습니다."}
    row = aligned[-1]; sample = row["sample"]; age = m["t0_us"] - sample["timestamp_us"]
    speed = sample.get("vehicle_speed_kmh")
    if age < 0 or age > PROFILE["can_max_age_us"] or age != row.get("age_us"):
        return {"status": "UNKNOWN", "message": "CAN 측정 시각·허용 지연을 확인하세요."}
    if "CAN:" + str(sample["timestamp_us"]) not in action["evidence_refs"]:
        return {"status": "NOT_CHECKED", "message": "이 행동에 CAN 측정 근거가 연결되지 않았습니다."}
    if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
        return {"status": "UNKNOWN", "message": "km/h 단위의 유효한 속도 측정이 필요합니다."}
    if code in ("START", "STOP"):
        # An instantaneous speed cannot refute an action still in progress.
        return {"status": "NOT_CHECKED", "message": "출발·정지 과정은 시작·완료 구간의 측정 연결이 필요합니다."}
    if PROFILE["stationary_max_kmh"] < speed < PROFILE["moving_min_kmh"]:
        return {"status": "UNKNOWN", "message": "저속 구간에서는 정지·주행을 확정하지 않습니다.", "speed_kmh": speed}
    solver = z3.Solver(); solver.set(timeout=PROFILE["solver_timeout_ms"])
    measured = z3.Real("measured_speed_kmh")
    solver.add(measured == z3.RealVal(str(speed)))
    solver.add(measured <= PROFILE["stationary_max_kmh"] if code == "HOLD" else measured >= PROFILE["moving_min_kmh"])
    checked = solver.check()
    return {"status": "PASS" if checked == z3.sat else "FAIL" if checked == z3.unsat else "UNKNOWN",
            "message": f"{speed:g} km/h 측정과 {'정지 유지' if code == 'HOLD' else '주행 지속'} 행동을 대조했습니다.",
            "speed_kmh": speed, "age_us": age, "measurement_timestamp_us": sample["timestamp_us"], "solver_status": str(checked).upper()}


def summarize(items):
    if any(r["status"] == "FAIL" for r in items): return "FAIL"
    if items and all(r["status"] == "NOT_CHECKED" for r in items): return "NOT_CHECKED"
    if any(r["status"] in ("UNKNOWN", "NOT_CHECKED") for r in items): return "UNKNOWN"
    return "PASS" if items else "NOT_APPLICABLE"


def evaluate(stored, row):
    """Project property results retain edit pointers and solver evidence."""
    from .studio_grounded_sequence import atom_key, source
    data = stored.get("property_input", {}); m = data.get("moment", {})
    coc = m.get("coc") or {}; actions = coc.get("observed_actions", [])
    definitions = row.get("constraints",[]); kinds = data.get("entity_kinds", {})
    records = [(tuple(r["key"]), r["truth"]) for r in data.get("facts", [])]
    model = Evidence(records, kinds); results = {}
    def save(pid, state, message, checks=(), sources=()):
        results[pid] = {"property_id": pid, "status": state, "message": message, "checks": list(checks), "sources": deepcopy(list(sources))}
    for pid, codes in CODE_MAP.items():
        issues = [r for r in row.get("review_items",[]) if r["code"] in codes]
        state = "FAIL" if any("CONTRADICTION" in r["code"] or r["code"] in ("IDENTITY_CONFLICT", "OBSERVATION_CONFLICT", "LIFECYCLE_CONFLICT") for r in issues) else "UNKNOWN" if issues else "PASS"
        save(pid, state, " ".join(dict.fromkeys(r["message"] for r in issues)) or "제공된 입력과 이전 요약 안에서 검사했습니다.", issues, [s for r in issues for s in r.get("sources", [])])
    if not data or "entities" not in coc:
        for pid, category, title in PROPERTIES:
            save(pid, "NOT_CHECKED", "대상·관계가 있는 구조화된 CoC·제약 입력이 필요합니다.")
    else:
        if not actions: save("B6", "NOT_CHECKED", "실제 행동이 없으므로 행동 위반을 판정하지 않습니다.")
        missing_required = [d for d in definitions if d["effect"] == "REQUIRE" and row["states"][d["condition_id"]]["active_obligation"] and not any(same_action(d, a) for a in actions)]
        if missing_required and not coc.get("action_observation_complete", False) and results["B6"]["status"] != "FAIL":
            save("B6", "UNKNOWN", "의무 행동이 목록에 없습니다. 관찰이 완전한지 확인하기 전에는 미수행으로 단정하지 않습니다.")
        if "SOLVER_UNKNOWN" in row["codes"]:
            for pid in ("B3", "B5", "B6", "B8"):
                if results[pid]["status"] == "PASS": save(pid, "UNKNOWN", "SMT가 시간 제한 안에 판정을 확정하지 못했습니다.")
        if not definitions: save("B4", "NOT_APPLICABLE", "비교할 조건 정의가 없습니다."); save("B5", "NOT_APPLICABLE", "유지·해제할 조건이 없습니다.")
        pre = [d for d in definitions if d["effect"] != "FORBID" and row["states"][d["condition_id"]]["state"] == "ACTIVE" and d["preconditions"] and any(same_action(d, a) for a in actions)]
        if not pre and results["B7"]["status"] != "FAIL": save("B7", "NOT_APPLICABLE", "실제 행동에 적용되는 필수 선행 조건이 없습니다.")
        posts = [d for d in definitions if d["expected_postconditions"]]
        queried = [q for q in row["verification"]["smt"]["results"] if q["query_id"].startswith("post_")]
        results["B3"]["checks"].extend(row["verification"]["relation_checks"]["results"])
        results["B6"]["checks"].extend(row["verification"]["condition_checks"]["results"])
        results["B5"]["checks"].extend({"condition_id":cid, **state} for cid,state in row["states"].items())
        results["B8"]["checks"].extend(queried)
        if results["B3"]["status"]=="FAIL":
            for pid in ("B6","B7","B8"):
                if results[pid]["status"]!="NOT_APPLICABLE":save(pid,"UNKNOWN","관찰 사실이 모순돼 이 사실에 의존하는 행동·선행·후행 검사를 확정하지 않습니다.",results[pid]["checks"])
        contexts=deepcopy(stored.get("postcondition_checks",[]))
        for c in contexts:
            if c["reason"]=="TIMING_REQUIRED":c["code"]="POSTCONDITION_TIMING_REQUIRED"
        if not posts: save("B8", "NOT_APPLICABLE", "정의된 기대 결과가 없습니다.")
        elif contexts:
            results["B8"]["checks"].extend(contexts)
            results["B8"]["sources"].extend(s for c in contexts for s in c["sources"])
            applicable=[c for c in contexts if c["status"]!="NOT_APPLICABLE"]
            pending=[c for c in applicable if c["status"]=="NOT_CHECKED"]
            if results["B8"]["status"]=="PASS" and (pending or not queried):
                state=("UNKNOWN" if queried else "NOT_CHECKED") if applicable else "NOT_APPLICABLE"
                save("B8",state," ".join(dict.fromkeys(c["message"] for c in pending or contexts)),results["B8"]["checks"],results["B8"]["sources"])
                results["B8"]["informational"]=bool(pending) and not any(c.get("code") for c in pending)
        elif not queried and results["B8"]["status"] == "PASS":
            save("B8", "NOT_CHECKED", "이전 실제 행동·완료 확인 시점이 연결된 기대 결과만 검사합니다.")
        bindings = coc.get("reason_bindings", []); checks = []; refs = []
        for i, binding in enumerate(bindings):
            src = source(m, "sequence_coc", "/reason_bindings/" + str(i), binding); refs.append(src)
            index = binding["action_index"]; excerpt = binding["explanation_excerpt"]
            if index >= len(actions) or not excerpt.strip() or excerpt not in coc.get("explanation", "") or not binding["reasons"]:
                checks.append({"status": "UNKNOWN", "message": "설명 원문·실제 행동·이유의 연결을 확인하세요."}); continue
            scoped = [d for d in definitions if same_action(d, actions[index])]
            relevant = {atom_key(g["atom"]) for d in scoped for g in d["activation_all_of"] + d["preconditions"]}
            action_scope={actions[index].get(k) for k in ("subject_ref","action_target_ref","movement_ref")}-{None}
            reason_keys={atom_key(g["atom"]) for g in binding["reasons"]}
            def related(key):
                return key in relevant or bool(set(key[1:])&action_scope) or (key[0] in ("SIGNAL_GREEN","SIGNAL_RED") and any(("APPLIES_TO",key[1],ref) in reason_keys for ref in action_scope))
            if not all(related(atom_key(g["atom"])) for g in binding["reasons"]):
                checks.append({"status": "UNKNOWN", "message": "이유가 해당 행동의 조건과 연결되지 않았습니다."}); continue
            checks.append(model.support(model.guards(binding["reasons"])))
        save("A1", summarize(checks) if bindings else "NOT_CHECKED", "설명에 연결된 이유를 독립 관찰 사실과 대조합니다." if bindings else "설명의 이유–행동 연결이 없습니다. 문장만으로 연결을 추측하지 않습니다.", checks, refs)
        checks = []; refs = []
        for i, a in enumerate(actions):
            if a["code"] not in ("ENTER", "START"): continue
            scoped = [d for d in definitions if same_action(d, a) and d["effect"] in ("ALLOW", "REQUIRE")]
            guards = [g for d in scoped for g in d["activation_all_of"] + d["preconditions"]]
            keys = {atom_key(g["atom"]) for g in guards if g["expected_truth"] == "TRUE"}
            target = a["action_target_ref"]; missing = []
            if kinds.get(target) not in ("LANE", "ZONE"):
                checks.append({"status": "UNKNOWN", "message": "진입·출발 경로가 연결되지 않아 체크리스트 적용을 보류합니다."}); continue
            if ("PATH_CLEAR", target, None) not in keys: missing.append({"predicate": "PATH_CLEAR", "target": target})
            for p, signal, _ in keys:
                if p == "SIGNAL_GREEN" and not any(("APPLIES_TO", signal, obj) in keys for obj in ("ego", target)):
                    missing.append({"predicate": "APPLIES_TO", "signal": signal, "target": target})
            checks.append({"status": "UNKNOWN" if missing else "PASS", "missing": missing, "profile_id": PROFILE["id"]})
            refs.append(source(m, "sequence_coc", "/observed_actions/" + str(i), a))
            refs.extend(source(m, "sequence_constraints", "/new_definitions/" + str(j), d) for j, d in enumerate((m.get("constraints") or {}).get("new_definitions", [])) if d in scoped)
        save("A2", summarize(checks), "진입·출발의 경로 비움과 녹색 신호의 적용성을 연구 체크리스트로 검사합니다. 조건 포함 여부와 사실의 참 여부는 별개입니다.", checks, refs)
        checks = []; refs = []
        action_keys = {(action, d["subject_ref"], d["action_target_ref"], d["movement_ref"]) for d in definitions if d["effect"] == "ALLOW" for action in d["actions"]}
        for code, actor, target, movement in sorted(action_keys, key=repr):
            a = {"code": code, "subject_ref": actor, "action_target_ref": target, "movement_ref": movement}
            allowed = [d for d in definitions if d["effect"] == "ALLOW" and same_action(d, a)]
            forbidden = [d for d in definitions if d["effect"] == "FORBID" and same_action(d, a)]
            ready = [z3.And(model.guards(d["activation_all_of"]) if d["activation_all_of"] else z3.BoolVal(False), z3.Not(model.guards(d["release_any_of"], True)), model.guards(d["preconditions"])) for d in allowed]
            blockers = []
            for d in forbidden:
                state = row["states"][d["condition_id"]]
                blockers.append(z3.BoolVal(True) if state["active_obligation"] else z3.BoolVal(False) if state["state"] in ("INACTIVE", "RELEASED") else model.atom(("ACTIVE", d["condition_id"], None)))
            check = model.support(z3.And(z3.Or(*ready), z3.Not(z3.Or(*blockers))))
            # A false conditional permission is a valid BLOCKED assessment,
            # not a false CoC claim or a violation by a recorded HOLD action.
            check["permission"] = "CONFIRMED" if check["status"] == "PASS" else "BLOCKED" if check["status"] == "FAIL" else "UNCONFIRMED"
            if check["status"] == "FAIL": check["status"] = "PASS"
            check.update(action=a, blocker_condition_ids=[d["condition_id"] for d in forbidden]); checks.append(check)
            refs.extend(s for s in stored["source_map"].values() if isinstance(s.get("value"),dict) and s["value"].get("condition_id") in {d["condition_id"] for d in allowed+forbidden})
        save("A3", summarize(checks), "조건별 허용을 합치고 같은 행동·대상·경로의 금지를 확인합니다. 허용 보류 자체는 관찰 행동의 오류가 아닙니다.", checks, refs)
        checks = [can_check(a, m) for a in actions]
        save("A4", summarize([c for c in checks if c["status"] != "NOT_APPLICABLE"]), "행동에 연결된 최신 과거 CAN 측정과 대조합니다. 영상 시점의 상태를 보증하지 않습니다.", checks, [source(m, "sequence_coc", "/observed_actions/" + str(i), a) for i, a in enumerate(actions)])
    ordered = [{**results[pid], "category": category, "title": title} for pid, category, title in PROPERTIES]
    return {"version": VERSION, "profile": deepcopy(PROFILE), "status": summarize([p for p in ordered if p["status"] != "NOT_APPLICABLE"]),
            "results": ordered, "counts": {state: sum(p["status"] == state for p in ordered) for state in ("PASS", "FAIL", "UNKNOWN", "NOT_CHECKED", "NOT_APPLICABLE")},
            "scope": "Prior/current scene only; finite summary; no unbounded liveness, perception or universal completeness certificate."}
