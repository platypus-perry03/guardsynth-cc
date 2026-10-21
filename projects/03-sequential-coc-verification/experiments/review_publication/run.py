"""Export an allowlisted, history-free reviewer tree from canonical project files."""
import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "PROJECT_REGISTRY.json").is_file())
OWNER = ROOT / "projects/03-sequential-coc-verification"
PUBLIC = OWNER / "artifacts/public"
RUNS = {
    "controlled": PUBLIC / "kiee-review-revision-001/controlled-scenarios-2026-10-01-001",
    "condition": PUBLIC / "kiee-review-revision-001/condition-model-2026-10-01-001",
    "terminal": PUBLIC / "kiee-review-revision-001/terminal-evidence-2026-10-01-001",
    "boundary": PUBLIC / "cross-scene-constraints-001/cross-scene-constraints-2026-10-12-001",
    "bounded": PUBLIC / "bounded-conformance-001/bounded-conformance-2026-10-12-001",
}
SOURCES = [
    "sequential_coc/" + name for name in (
        "__init__.py", "contract_ir.py", "contract_compiler.py", "extract_windows.py",
        "stateful_checker.py", "event_local_checker.py", "uppaal_generator.py", "run_uppaal.py",
        "mutation_generator.py")
] + [
    "kiee_review_revision/scenario_evaluation.py", "kiee_review_revision/condition_model.py",
    "kiee_review_revision/audit_terminal_evidence.py",
    "kiee_review_revision/tests/test_scenario_evaluation.py",
    "kiee_review_revision/tests/test_condition_model.py",
    "kiee_review_revision/tests/test_terminal_evidence.py",
    "cross_scene_constraints/run.py", "cross_scene_constraints/test_cross_scene_constraints.py",
    "bounded_conformance/enumerate.cpp", "bounded_conformance/formula_oracle.hpp",
]
REDACT_KEYS = {"command", "uppaal_run"}
IDENTITY = re.compile(
    r"jinhyun|jinkimh|guardsynth|/home/|/Users/|github\.com/|git@github|"
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|NRF-2023R1A2C1006639|RS-2024-00436773",
    re.IGNORECASE,
)
FORBIDDEN_NAMES = re.compile(r"response-to-reviewer|reviewer[-_]0?[123]|REVIEWER_|\.git(?:/|$)", re.I)
ALLOWED_EXTENSIONS = {".py", ".cpp", ".hpp", ".json", ".jsonl", ".csv", ".xml", ".q", ".md"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def strip_execution_paths(value):
    if isinstance(value, dict):
        return {k: strip_execution_paths(v) for k, v in value.items() if k not in REDACT_KEYS}
    if isinstance(value, list):
        return [strip_execution_paths(v) for v in value]
    return value


def scan(path, data):
    """Reject risky content; do not silently mask unexpected findings."""
    if path.suffix not in ALLOWED_EXTENSIONS or FORBIDDEN_NAMES.search(path.as_posix()):
        raise ValueError("Disallowed export path: " + path.as_posix())
    if any(part in {"restricted", "data", "paper", "source_snapshot", "__pycache__"} for part in path.parts):
        raise ValueError("Excluded namespace: " + path.as_posix())
    text = data.decode("utf-8")
    if IDENTITY.search(text) or re.search(r"\bscene-\d{4}\b", text):
        raise ValueError("Identifying or natural-scene content in: " + path.as_posix())


README = """# Sequential consistency: executable research artifact

This tree contains authored symbolic inputs, executable checking code, UPPAAL
models/queries, and retained results. It is exported from maintained research
sources, plus the original categorical human judgments under anonymous IDs.
It contains no natural CoC text, camera video, trajectory files, personal names,
free-text review notes, manuscript, peer-review letters, or original Git history.

## Reproduce

Requirements: Python 3.10 or newer and a C++17 compiler named `c++`.
The default run uses only the Python standard library and the compiler:

```sh
python3 -B reproduce.py --output /tmp/consistency-reproduction
```

It verifies the file inventory, regenerates the original 40 regression pairs byte
for byte, recomputes human Fleiss kappa and Gwet AC1, reconstructs all 144/81
authored inputs and model files, reruns Python comparisons, and enumerates all 35,042,928 bounded sequences
plus the separate 5,256-case processing-fault control. Outputs must be written to
a new directory. The full bounded enumeration is native C++, not a UPPAAL search.

To rerun the actual model checker as well, supply your own working installation
of UPPAAL/verifyta (the retained runs used version 5.0.0):

```sh
python3 -B reproduce.py --output /tmp/consistency-with-solver --verifyta /path/to/verifyta
```

This additionally checks 144 original models, their 144 terminal-query diagnoses,
144 condition-linked models, and 162 boundary models. No solver executable,
license file, or third-party dataset is distributed here. The unused natural
table-reader functions in the original code need pandas and separately obtained
data; they are outside these reproduction commands. Its pandas import is deferred
in this export, without changing the checker or parser computations.

## Evidence and interpretation

| Material | What can be checked |
|---|---|
| `evidence/regression` | Original 40 structured reference/mutation pairs and deterministic generator; full-history 40/40 versus current-event 20/40 |
| `evidence/human` | Preserved Korean review instructions, anonymous 27-subject x 4-rater categorical judgments, agreement statistics and rater distributions |
| `evidence/controlled` | All 144 authored text/frame cases; original full-history agreement 96/144; local/window comparisons; FSM 144/144; automatic parser yields UNKNOWN in all cases |
| `evidence/condition` | Same-case post-development retest, 144/144; issue location/obligation/reason records |
| `evidence/terminal` | Original prefix traces differ on uncertainty reasons in 24 cases; terminal-query diagnosis agrees in all 144 |
| `evidence/boundary` | All 81 authored cases; state carry 81/81 versus boundary reset 14/81 |
| `evidence/bounded` | 35,042,928 unselected sequences, zero disagreements; all 1,884 fault-control disagreements retained separately |

Inputs, labels, models and the separate formula evaluator share research
authorship. These are regression/feasibility and bounded implementation-conformance
results, not independent semantic gold, natural detection accuracy, or vehicle
safety evidence. The condition-linked and boundary models have different lifecycle
policies; they are not asserted to be equivalent. An explicit P2 release-command
input and quantitative timing guarantees are outside these primary models.

The 40 pairs are controlled synthetic IR, not natural source sentences. Their
generator checks its expected postconditions using the checkers themselves; this
is a regression test, not an independent detection-accuracy experiment. The broad
natural-data pipeline drivers are unnecessary for replaying this generator.

The anonymous ratings retain the three original categorical fields, including
exact action-sequence strings. Subject IDs G01-G27 follow the preserved analysis
order and raters A-D match its distributions. Original review IDs, filenames,
initials, free-text notes and ID mappings are excluded. Release authorization for
the anonymous categorical table was confirmed before preparing this export.
The statistical functions are extracted unchanged from the maintained analysis;
the default replay verifies its retained coefficients and exact pair enumeration.

`evidence/human/REVIEW_PROTOCOL.md` is the unchanged retained instruction document.
Its historical WAITING status and two-form A/B saving instructions are preserved;
it is not evidence of all four raters' training or adjudication procedures. No new
human evaluation or natural semantic gold is implied. Trajectory comparison and
the 134-event response analysis cannot be fully replayed without separately
obtained source data. Historical model revisions, generation prompts/settings,
and the quality-score formula/threshold remain unrecoverable.

`artifact_manifest.json` records every exported file hash, original byte hashes,
and any export-only transformation. Original execution commands with workstation
paths are omitted from exported result records. Scientific inputs, expected labels,
predictions and measured results are preserved. The historical paper specification
and original run manifests are kept by the authors, rather than copied here.

The authors retain ownership of the supplied research material. This review
artifact does not add a separate open-source license; public redistribution terms
must be established separately. UPPAAL is supplied independently by the reader.
"""


def build(run_id):
    output = PUBLIC / "review-publication-001" / run_id
    output.mkdir(parents=True, exist_ok=False)
    payload = output / "payload"
    inventory = {}
    local_inputs = []

    def put(name, data, source=None, transformation="NONE"):
        relative = Path(name)
        scan(relative, data)
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = {"sha256": sha(data), "bytes": len(data), "transformation": transformation}
        if source is not None:
            entry["source_sha256"] = sha(source.read_bytes())
            local_inputs.append({"path": str(source.relative_to(ROOT)), "sha256": entry["source_sha256"]})
        inventory[name] = entry

    def copy(source, name, structured=False):
        data = source.read_bytes()
        transformation = "NONE"
        if structured:
            if source.suffix == ".jsonl":
                data = b"".join((json.dumps(strip_execution_paths(json.loads(line)), ensure_ascii=False) + "\n").encode()
                                for line in data.decode().splitlines())
            else:
                data = json_bytes(strip_execution_paths(json.loads(data)))
            transformation = "REMOVE_EXECUTION_PATH_FIELDS_AND_SERIALIZE_JSON"
        put(name, data, source, transformation)

    put("README.md", README.encode())
    # Original modules use the presence of this file to locate their import root.
    put("PROJECT_REGISTRY.json", json_bytes({"artifact_kind": "AUTHORED_SYMBOLIC_REPRODUCTION", "schema_version": 1}))
    copy(Path(__file__).with_name("reproduce.py"), "reproduce.py")
    copy(Path(__file__).with_name("agreement_replay.py"), "agreement_replay.py")
    for name in SOURCES:
        source = OWNER / "experiments" / name
        data = source.read_bytes()
        transformation = "NONE"
        if name == "sequential_coc/extract_windows.py":
            text = data.decode()
            assert text.count("import pandas as pd\n") == 1
            assert text.count("    frame = pd.read_parquet(") == 2
            text = text.replace("import pandas as pd\n", "")
            text = text.replace("    frame = pd.read_parquet(", "    import pandas as pd\n    frame = pd.read_parquet(")
            data = text.encode()
            transformation = "DEFER_PANDAS_IMPORT_TO_TWO_UNUSED_NATURAL_TABLE_READERS"
        put("experiments/" + name, data, source, transformation)

    regression = OWNER / "artifacts/restricted/sequential-coc-consistency-v1/mutations.jsonl"
    for line in regression.read_text().splitlines():
        pair = json.loads(line)
        for side in ("original", "mutated"):
            for event in pair[side]["events"]:
                if event["provenance"] != "CONTROLLED_SYNTHETIC_IR" or any(
                    event.get(key) is not None for key in ("trigger", "satisfaction_condition", "release_condition", "source_text", "text")
                ):
                    raise ValueError("Regression export must contain only controlled synthetic IR")
    copy(regression, "evidence/regression/mutations.jsonl")

    review = OWNER / "artifacts/restricted/sequential-coc-consistency-v1/review"
    copy(review / "REVIEW_PROTOCOL.md", "evidence/human/REVIEW_PROTOCOL.md")
    files = sorted(review.glob("contract_review_[AB](*).csv"))
    panel = []
    for source in files:
        with source.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        indexed = {row["review_id"]: row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError("Duplicate original review ID")
        panel.append(indexed)
        local_inputs.append({"path": str(source.relative_to(ROOT)), "sha256": sha(source.read_bytes())})
    if len(panel) != 4 or len(panel[0]) != 27 or any(set(p) != set(panel[0]) for p in panel):
        raise ValueError("Expected the preserved complete four-rater panel")
    spec = importlib.util.spec_from_file_location("agreement_replay", Path(__file__).with_name("agreement_replay.py"))
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=replay.HEADERS, lineterminator="\n")
    writer.writeheader()
    for i, rid in enumerate(sorted(panel[0]), 1):
        for rater, records in zip("ABCD", panel):
            writer.writerow({"subject_id": f"G{i:02d}", "rater_id": rater,
                             **{field: records[rid][field] for field in replay.FIELDS}})
    put("evidence/human/ratings.csv", stream.getvalue().encode())
    source = OWNER / "experiments/kiee_review_revision/analyze_reviewer_agreement.py"
    tree = ast.parse(source.read_text())
    functions = [ast.get_source_segment(source.read_text(), node) for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in {"coefficients", "pairwise_exact_check"}]
    if len(functions) != 2:
        raise ValueError("Expected the two unchanged agreement functions")
    code = "from collections import Counter\nfrom fractions import Fraction\nfrom itertools import combinations\n\n\n" + "\n\n\n".join(functions) + "\n"
    put("agreement_coefficients.py", code.encode(), source, "EXTRACT_TWO_UNCHANGED_PURE_STATISTICAL_FUNCTIONS")
    namespace = {}
    exec(code, namespace)
    agreement = replay.calculate(payload / "evidence/human/ratings.csv", namespace["coefficients"], namespace["pairwise_exact_check"])
    retained = OWNER / "artifacts/restricted/kiee-review-revision-001/reviewer-agreement-2026-10-12-001/RESULT.json"
    if agreement["fields"] != json.loads(retained.read_text())["fields"]:
        raise ValueError("Anonymous panel differs from retained agreement analysis")
    local_inputs.append({"path": str(retained.relative_to(ROOT)), "sha256": sha(retained.read_bytes())})
    put("evidence/human/agreement.json", json_bytes(agreement))

    filenames = {
        "controlled": ["cases.json", "scores.json", "RESULT.json", "results.jsonl", "semantic_mismatches.json", "uppaal_mismatches.json"],
        "condition": ["RESULT.json", "results.json"],
        "terminal": ["RESULT.json", "terminal_results.json"],
        "boundary": ["cases.json", "protocol.json", "RESULT.json", "results.json"],
        "bounded": ["RESULT.json", "protocol.json", "condition_frozen.xml", "boundary_frozen.xml", "frozen_targets.hpp", "stdout.jsonl", "mismatches.jsonl", "fault_control_mismatches.jsonl"],
    }
    for key, names in filenames.items():
        for name in names:
            source = RUNS[key] / name
            copy(source, f"evidence/{key}/{name}", structured=source.suffix in {".json", ".jsonl"})
        # Only models and query files: no manuscript snapshots or raw process logs.
        if key != "bounded":
            for source in sorted(RUNS[key].rglob("*")):
                if source.is_file() and source.suffix in {".xml", ".q"}:
                    copy(source, "evidence/" + key + "/" + str(source.relative_to(RUNS[key])))

    manifest = {"schema_version": 2, "scope": "SYMBOLIC_REPRODUCTION_AND_ANONYMOUS_CATEGORICAL_REVIEW",
                "contains_natural_source_data": False, "contains_peer_review_material": False,
                "contains_anonymous_human_ratings": True, "contains_git_history": False, "files": inventory}
    put("artifact_manifest.json", json_bytes(manifest))
    local_manifest = {"project_id": "sequential-coc-verification", "task_id": "review-publication",
                      "status": "PREPARED", "created_at": datetime.now(timezone.utc).isoformat(),
                      "inputs": local_inputs, "payload_files": len(inventory),
                      "publication_branch": "review-artifact", "published": False,
                      "anonymity_scope": "Direct identifiers and excluded namespaces checked; prior public exposure is not undone."}
    (output / "RUN_MANIFEST.json").write_bytes(json_bytes(local_manifest))
    (output / "RESULT.json").write_bytes(json_bytes({"status": "PREPARED", "payload_files": len(inventory), "identity_scan": "PASS", "zip_created": False}))
    (output / "REPORT_KO.md").write_text(
        "# 심사용 Git 공개 범위\n\n"
        "공개 후보에는 기존 작성 144건·경계 81건·유한 전수 대조에 더해, 원 40쌍과 생성기, 보존 검토 지침, "
        "공개 근거나 동의를 확인한 4인×27장면 익명 범주 판정표와 κ·AC1 재계산 코드를 포함한다. "
        "원 CoC·영상·궤적·실명/이니셜·자유 메모·원 ID 대응·원고·답변서·심사 의견·기존 Git 이력은 제외한다.\n\n"
        "`payload/`는 허용 목록으로 생성한 배포 결과다. 코드는 원래 실험 디렉터리가 유지보수 원본이며, "
        "새 연구 구현을 이 경로에서 유지하지 않는다. 자연 자료 기반 결과의 완전 재현은 이 공개 범위에 포함하지 않는다.\n\n"
        "40쌍 생성기는 검사기를 이용해 기대 사후조건을 확인하므로 독립 검출 성능의 근거가 아니다. "
        "검토 지침은 원문의 대기 상태와 A/B 두 양식 설명을 보존했다. 네 검토자의 교육·합의 절차를 복원한 것으로 해석하지 않는다.\n\n"
        "추가본은 아직 커밋·푸시하지 않았다. 승인 후 기존 `review-artifact` 브랜치에 반영하고, "
        "고정 커밋 방식의 익명 미러도 갱신한 뒤 실제 열람 범위를 확인해야 한다. 원고·답변서에는 그 후 반영한다. "
        "생성 모델의 실행별 버전, 생성 지시문·설정, 품질 점수 계산식·임계값은 여전히 복원 불가다.\n"
    )
    print(json.dumps({"output": str(output.relative_to(ROOT)), "files": len(inventory), "scan": "PASS"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}", args.run_id):
        parser.error("Invalid run ID")
    build(args.run_id)
