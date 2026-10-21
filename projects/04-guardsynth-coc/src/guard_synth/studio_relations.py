"""Scene relation grammar shared by generation checks and Studio editors."""
from copy import deepcopy

VERSION = "studio-relations-v1"
KIND_LABELS = {"EGO":"자차", "VEHICLE":"차량", "PEDESTRIAN":"보행자", "CYCLIST":"자전거", "SIGNAL":"신호", "ZONE":"구역", "LANE":"차로", "OBSTACLE":"장애물", "SURFACE":"노면", "VISIBILITY":"시야"}
PHYSICAL = [k for k in KIND_LABELS if k != "VISIBILITY"]
ACTORS = ["EGO", "VEHICLE", "PEDESTRIAN", "CYCLIST"]
AREAS = ["ZONE", "LANE"]
GROUPS = {"STATE":"대상의 상태", "DIRECTION":"방향", "CONTAINMENT":"포함·점유", "TOPOLOGY":"인접·경계", "APPLICATION":"적용", "PATH":"경로·통과"}


def rule(group, subjects, objects=(), arity="UNARY", **extra):
    return {"group":group, "subject_kinds":list(subjects), "object_kinds":list(objects), "arity":arity, **extra}


RULES = {
    "SIGNAL_RED":rule("STATE", ["SIGNAL"]), "SIGNAL_GREEN":rule("STATE", ["SIGNAL"]),
    "PATH_CLEAR":rule("STATE", AREAS), "ZONE_CLOSED":rule("STATE", AREAS),
    "STOPPED":rule("STATE", ACTORS),
    "VISIBILITY_INSUFFICIENT":rule("STATE", ["EGO", "VISIBILITY"], ["EGO"], "OPTIONAL"),
    "SURFACE_RISK":rule("STATE", ["EGO", "SURFACE", "LANE", "ZONE"], ["EGO"], "OPTIONAL"),
    **{p:rule("DIRECTION", PHYSICAL, PHYSICAL, "BINARY", inverse=q, reference_frame="CURRENT_EGO_FORWARD") for p,q in [("LEFT_OF","RIGHT_OF"),("RIGHT_OF","LEFT_OF"),("AHEAD_OF","BEHIND_OF"),("BEHIND_OF","AHEAD_OF")]},
    "IN":rule("CONTAINMENT", PHYSICAL, AREAS, "BINARY"),
    "OCCUPIES":rule("CONTAINMENT", PHYSICAL, AREAS, "BINARY"),
    "ADJACENT_TO":rule("TOPOLOGY", PHYSICAL, PHYSICAL, "BINARY", symmetric=True),
    "BOUNDARY_OF":rule("TOPOLOGY", PHYSICAL, AREAS, "BINARY"),
    "APPLIES_TO":rule("APPLICATION", ["SIGNAL"], ["EGO", *AREAS], "BINARY"),
    "PATH_CONFLICT":rule("PATH", PHYSICAL, ["EGO", *AREAS], "BINARY"),
    "PASSAGE_COMPLETE":rule("PATH", ["EGO"], AREAS, "OPTIONAL"),
}


def grammar():
    return {"version":VERSION, "groups":deepcopy(GROUPS), "rules":deepcopy(RULES)}


def generation_atom_schema(context):
    """Responses union: each predicate offers only compatible supplied IDs."""
    entries=context.get("inherited_entities",[])+context.get("previous_entities",[])+context.get("coc",{}).get("entities",[])
    entities={e["entity_id"]:e["kind"] for e in entries}
    branches=[]
    for predicate,r in RULES.items():
        subjects=sorted(ref for ref,kind in entities.items() if kind in r["subject_kinds"])
        objects=sorted(ref for ref,kind in entities.items() if kind in r["object_kinds"])
        if not subjects or r["arity"]=="BINARY" and not objects: continue
        target=({"type":"null"} if r["arity"]=="UNARY" or not objects else
                {"type":["string","null"] if r["arity"]=="OPTIONAL" else "string",
                 "enum":objects+([None] if r["arity"]=="OPTIONAL" else [])})
        branches.append({"type":"object","properties":{
            "predicate":{"type":"string","enum":[predicate]},
            "subject_ref":{"type":"string","enum":subjects},"object_ref":target},
            "required":["predicate","subject_ref","object_ref"],"additionalProperties":False})
    return {"anyOf":branches} if branches else None


def atom_error(atom, entities):
    p, a, b = (atom.get(k) for k in ("predicate", "subject_ref", "object_ref"))
    r = RULES.get(p)
    if not r: return "지원하지 않는 확인 관계입니다."
    def label(ref):
        e = entities.get(ref, {})
        return e.get("description") or KIND_LABELS.get(e.get("kind"), "연결되지 않은 대상")
    def allowed(kinds): return "·".join(KIND_LABELS[k] for k in kinds)
    if a not in entities or entities[a]["kind"] not in r["subject_kinds"]:
        return f"관찰 대상 ‘{label(a)}’의 종류가 맞지 않습니다. {allowed(r['subject_kinds'])} 대상을 선택하세요."
    if r["arity"] == "UNARY" and b is not None:
        return "이 항목은 한 대상의 상태입니다. 비교·적용 대상이 필요하지 않습니다."
    if r["arity"] == "BINARY" and b is None:
        return f"이 관계에는 두 번째 대상이 필요합니다. {allowed(r['object_kinds'])} 대상을 선택하세요."
    if b is not None and (b not in entities or entities[b]["kind"] not in r["object_kinds"]):
        return f"비교·적용 대상 ‘{label(b)}’의 종류가 맞지 않습니다. {allowed(r['object_kinds'])} 대상을 선택하세요."
    return None


def atoms(candidate):
    for i, value in enumerate(candidate.get("relations", [])):
        yield f"/relations/{i}", value
    for i, value in enumerate(candidate.get("facts", [])):
        yield f"/facts/{i}/atom", value["atom"]
    for i, definition in enumerate(candidate.get("new_definitions", [])):
        for field in ("activation_all_of", "release_any_of", "preconditions", "expected_postconditions"):
            for j, guard in enumerate(definition[field]): yield f"/new_definitions/{i}/{field}/{j}/atom", guard["atom"]
    for i, binding in enumerate(candidate.get("reason_bindings", [])):
        for j, guard in enumerate(binding["reasons"]): yield f"/reason_bindings/{i}/reasons/{j}/atom", guard["atom"]


def errors(candidate, context=None):
    context = context or {}
    entries = context.get("inherited_entities", []) + context.get("previous_entities", []) + context.get("coc", {}).get("entities", []) + candidate.get("entities", [])
    entities = {e["entity_id"]:e for e in entries}
    return [{"path":path, "message":message} for path, atom in atoms(candidate) if (message := atom_error(atom, entities))]


def require_valid(candidate, context=None):
    found = errors(candidate, context)
    if found: raise ValueError(found[0]["path"] + ": " + found[0]["message"])
