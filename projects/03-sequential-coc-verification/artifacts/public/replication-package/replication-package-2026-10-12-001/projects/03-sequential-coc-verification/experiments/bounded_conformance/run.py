"""Bounded formula/implementation conformance, not independent semantic gold."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "PROJECT_REGISTRY.json").exists())
OWNER = ROOT / "projects/03-sequential-coc-verification"
SOURCE = Path(__file__).resolve().parent


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(output):
    condition_path = OWNER / "experiments/kiee_review_revision/condition_model.py"
    boundary_path = OWNER / "experiments/cross_scene_constraints/run.py"
    condition = load(condition_path, "frozen_condition")
    boundary = load(boundary_path, "frozen_boundary")
    encoded = {"event_ids": ["e0", "e1", "e2"], "obligation_ids": ["A", "B"],
               "actions": [0, 1, 2], "new_obligations": [0, 1, -1], "preconditions": [-1] * 3,
               "observations": [-1] * 6, "creates": [0, 1, -1], "carry": [2] * 6, "persist": [0] * 6}
    output.mkdir(parents=True, exist_ok=False)
    bodies = {}
    for name, module in [("condition", condition), ("boundary", boundary)]:
        xml = module.model_bytes(encoded)
        (output / (name + "_frozen.xml")).write_bytes(xml)
        declaration = ET.fromstring(xml).find("declaration").text
        bodies[name] = declaration[declaration.index("void step()") :]
    common = """int K; int actions[3]{}, creates[3]{}, preconditions[3]{};
int observations[6]{},carry[6]{},persist[6]{};
bool active[2]{},linked[2]{}; int known[2]{-1,-1}; int idx=0,precondition=-1;
bool bad=false,missing=false,bad_hold=false,bad_pre=false;
int first_bad_idx=-1,first_missing_idx=-1,first_bad_obligation=-1,first_missing_obligation=-1;
"""
    sticky = bodies["condition"].replace("active[j] = false;", "active[j] = true;")
    assert sticky != bodies["condition"] and bodies["condition"].count("active[j] = false;") == 1
    header = "// Exact frozen XML step functions; only declarations are wrapped for native execution.\n"
    for name, body in [("ConditionTarget", bodies["condition"]), ("BoundaryTarget", bodies["boundary"]), ("StickyConditionTarget", sticky)]:
        header += "struct " + name + " {\n" + common + name + "(int k):K(k){}\n" + body + "\n};\n"
    (output / "frozen_targets.hpp").write_text(header)
    profiles = [("condition-k1-n3", 72, 72, 3), ("condition-k2-n3", 324, 324, 3),
                ("boundary-k1-n3", 24, 120, 3), ("boundary-k2-n2", 108, 1836, 2)]
    protocol = {"project_id": "sequential-coc-verification", "test_kind": "BOUNDED_UNSELECTED_FORMULA_IMPLEMENTATION_CONFORMANCE",
                "profiles": [{"name": name, "first_alphabet": first, "next_alphabet": nxt, "maximum_length": length,
                              "case_count": sum(first * nxt ** i for i in range(length))} for name, first, nxt, length in profiles],
                "actions": "STOP, WAIT, GO, YIELD; YIELD maps to non-GO STOP in the frozen IR",
                "alphabet": "creation=none/each obligation, evidence per condition=U/F/T; condition profile additionally precondition=U/F/T; boundary first event=no boundary, later=no boundary or all obligations assigned VERIFIED-point/VERIFIED-persistent/ENDED/UNCERTAIN",
                "oracle": "Prefix quantification and backwards evidence/creation searches, in formula_oracle.hpp; no monitor step or state-update function is shared",
                "comparison": "Final active/known/linked state, cumulative bad/missing and both first event/obligation records; every shorter prefix is itself included",
                "scope": "Encoded deterministic step semantics, not XML frontend acceptance, automata search, natural extraction or physical validity; P2 has no explicit release-command input; P4 handled as separate sticky-release processing fault",
                "independence": "Same research authorship; no independent semantic gold. Finite Cartesian product has no output-based filtering.",
                "failure_policy": "Every disagreement is saved; no case removal or label correction",
                "fault_control": {"profile": "condition-k1", "maximum_length": 2, "cases": 72 + 72 ** 2,
                                  "mutation": "only active[j]=false on known true is changed to active[j]=true"}}
    save(output / "protocol.json", protocol)
    sources = [condition_path, boundary_path, SOURCE / "formula_oracle.hpp", SOURCE / "enumerate.cpp", Path(__file__),
               OWNER / "paper/manuscript/latex-kiee-review-2022-coc-audit-revision-v01/sections/04-problem.tex"]
    manifest = {"project_id": "sequential-coc-verification", "task_id": "bounded-conformance", "status": "PREPARED",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "repository_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "pinning": "Working source hashes are authoritative; repository HEAD alone does not identify uncommitted model files.",
                "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in sources],
                "prepared_files": {p.name: digest(p) for p in output.iterdir() if p.is_file()},
                "independent_semantic_gold": False}
    save(output / "RUN_MANIFEST.json", manifest)
    print(json.dumps({"status": "PREPARED", "profiles": protocol["profiles"]}))


def evaluate(output):
    manifest = json.loads((output / "RUN_MANIFEST.json").read_text())
    assert manifest["status"] == "PREPARED"
    assert all(digest(ROOT / x["path"]) == x["sha256"] for x in manifest["inputs"])
    assert all(digest(output / name) == sha for name, sha in manifest["prepared_files"].items())
    command = ["c++", "-std=c++17", "-O2", "-I", str(output), "-I", str(SOURCE), str(SOURCE / "enumerate.cpp"), "-o", str(output / "enumerator")]
    build = subprocess.run(command, capture_output=True, text=True)
    (output / "compile_stdout.txt").write_text(build.stdout)
    (output / "compile_stderr.txt").write_text(build.stderr)
    build.check_returncode()
    with (output / "stdout.jsonl").open("w") as stdout, (output / "stderr.txt").open("w") as stderr:
        process = subprocess.run([str(output / "enumerator"), str(output / "mismatches.jsonl"), str(output / "fault_control_mismatches.jsonl")], stdout=stdout, stderr=stderr, timeout=1800)
    process.check_returncode()
    rows = [json.loads(s) for s in (output / "stdout.jsonl").read_text().splitlines()]
    protocol = json.loads((output / "protocol.json").read_text())
    assert len(rows) == 5
    for row, expected in zip(rows[:4], protocol["profiles"]):
        assert row["profile"] == expected["name"] and row["cases"] == expected["case_count"]
    result = {"status": "COMPLETED", "profiles": rows[:4], "case_count": sum(r["cases"] for r in rows[:4]),
              "mismatches": sum(r["mismatches"] for r in rows[:4]), "fault_control": rows[4],
              "independent_semantic_gold": False, "actual_uppaal_search_rerun": False}
    save(output / "RESULT.json", result)
    table = "\n".join(f"| {r['profile']} | {r['cases']:,} | {r['mismatches']:,} |" for r in rows)
    (output / "REPORT_KO.md").write_text(f"""# 유한 사건열 전수 적합성 시험

고정한 두 모델의 실제 XML에서 step 함수를 변경 없이 추출하여 C++로 실행했다. 별도 판정기는 전체 접두열에서 최근 증거ㆍ의무 생성과 과거 해제를 직접 계산하며 상태 갱신 함수를 공유하지 않는다. 생성은 유한 직적의 전수 열거로 기대 결과에 따른 사례 선별이 없다.

| profile | 사건열 수 | 불일치 |
|---|---|---|
{table}

주 시험 총 {result['case_count']:,}건, 불일치 {result['mismatches']:,}건. 마지막 행은 주석 오류가 아닌 의도적 P4 처리 고장 대조군이며 주 시험 분모에 합산하지 않는다. 모든 불일치는 별도 JSONL에 보존했다. 첫 경계 없음, 의무 1/2개, 길이 상한과 세부 알파벳은 protocol.json에 고정했다. YIELD는 현 IR의 STOP과 같은 비진행 코드로 투영된다. P2의 별도 해제 명령은 인터페이스에 없어 평가하지 않는다.

UPPAAL 탐색기를 새로 실행한 시험은 아니며 실제 XML의 이산 step 의미를 수식 판정과 비교한 native 적합성 시험이다. 기존 144건/81건의 실제 verifyta 실행과 구분한다. 같은 연구 작성자가 두 경로에 관여했으므로 외부 독립 정답이나 명세의 현실 타당성을 입증하지 않는다. R3-7의 사례 선별 순환성에 대한 구조적 부분 대응이며 자연 의미 평가·독립 작성 역할의 한계는 남는다.
""")
    assert all(digest(ROOT / x["path"]) == x["sha256"] for x in manifest["inputs"])
    manifest.update(status="COMPLETED", completed_at=datetime.now(timezone.utc).isoformat(), command=command,
                    compiler=subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
                    outputs={p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != "RUN_MANIFEST.json"})
    save(output / "RUN_MANIFEST.json", manifest)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["prepare", "evaluate"], required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}", args.run_id):
        parser.error("Invalid owner-scoped run ID")
    output = OWNER / "artifacts/public/bounded-conformance-001" / args.run_id
    (prepare if args.stage == "prepare" else evaluate)(output)
