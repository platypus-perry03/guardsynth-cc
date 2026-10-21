"""Archive original-method checks without turning native outputs into action labels."""

import argparse
import ast
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[4]
PROTOCOL = Path(__file__).with_name("protocol_v0_1.json")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record(path):
    return {
        "checkout": str(path),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip(),
        "origin": subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=path, text=True
        ).strip(),
    }


def cohort_record(path, family):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    groups = collections.defaultdict(list)
    for row in rows:
        image = row.get("image_pixel_sha256", row.get("image_sha256"))
        label = row["response"] if "response" in row else row["example"]["target"]
        groups[(image, row["prompt"])].append(label)
    return {
        "family": family,
        "path": str(path),
        "sha256": sha256(path),
        "rows": len(rows),
        "distinct_image_and_prompt_groups": len(groups),
        "groups_with_conflicting_reference_labels": sum(
            len(set(labels)) > 1 for labels in groups.values()
        ),
        "maximum_correct_for_one_fixed_output_per_identical_input": sum(
            collections.Counter(labels).most_common(1)[0][1]
            for labels in groups.values()
        ),
        "scope": "Input-information audit; not a measured external-model score",
    }


def nl2tl_demo(args, output):
    import torch
    import transformers
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    notebook = args.nl2tl / "Run.ipynb"
    cells = json.loads(notebook.read_text())["cells"]
    snippets = ["".join(cell["source"]) for cell in cells if cell["cell_type"] == "code"]
    tree = ast.parse(next(code for code in snippets if "test_sentence =" in code))
    cases = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "test_sentence" for t in node.targets)
    )
    initial = "At some point (prop_1), and at some point (prop_2), and always do not (prop_4)."
    prefix = "Transform the following sentence into Signal Temporal logic: "
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, local_files_only=True, model_max_length=1024
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.checkpoint, local_files_only=True
    ).to("cuda:0")
    predictions = []
    for sentence in [initial] + cases:
        inputs = tokenizer(
            [prefix + sentence], max_length=1024,
            truncation=True, return_tensors="pt"
        ).to("cuda:0")
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **inputs, num_beams=8, do_sample=True, max_length=128
            )
        predictions.append({
            "input": sentence,
            "output": tokenizer.batch_decode(generated, skip_special_tokens=True)[0],
            "elapsed_seconds": time.monotonic() - started,
        })
    record = {
        "status": "NATIVE_DEMO_EXECUTED",
        "scope": "Official notebook demonstration; no candidate-selection score",
        "source_notebook_sha256": sha256(notebook),
        "checkpoint_files": {
            p.name: sha256(p) for p in args.checkpoint.iterdir() if p.is_file()
        },
        "tokenizer": "Official t5-base downloaded separately, loaded locally",
        "runtime": {"torch": torch.__version__, "transformers": transformers.__version__},
        "seed": 42,
        "generation": {"num_beams": 8, "do_sample": True, "max_length": 128},
        "predictions": predictions,
        "human_correction": False,
        "our_augmentation": False,
    }
    (output / "nl2tl_native_demo.json").write_text(json.dumps(record, indent=2) + "\n")
    return {"status": record["status"], "demonstration_cases": len(predictions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scratch", type=Path, default=Path("/tmp"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--nl2spec-attempt", type=Path, required=True)
    parser.add_argument("--gpu", type=int, default=2)
    args = parser.parse_args()
    prefix = args.scratch / "guardsynth-baseline-20261007"
    for name in ["nl2spec", "nl2tl", "drivelm", "drivevlm"]:
        setattr(args, name, Path(str(prefix) + "-" + name))
    memory = subprocess.check_output([
        "nvidia-smi", f"--id={args.gpu}", "--query-gpu=memory.used",
        "--format=csv,noheader,nounits"
    ], text=True)
    if int(memory.strip()) > 100:
        raise SystemExit("Selected GPU is occupied; refusing to start.")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    output = ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-external-methods-001" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(PROTOCOL.read_text())
    manifest = {
        "project_id": "guardsynth-coc",
        "experiment_id": protocol["experiment_id"],
        "run_id": args.run_id,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol": protocol,
        "source_checkouts": {name: source_record(getattr(args, name)) for name in ["nl2spec", "nl2tl", "drivelm", "drivevlm"]},
        "runner_sha256": sha256(Path(__file__)),
        "python": sys.version,
        "gpu_index": args.gpu,
    }
    (output / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    base = ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001"
    other = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001'
    cohorts = [
        cohort_record(base / "temporal-training-data-2026-09-29-001/test_p0.jsonl", "temporal"),
        cohort_record(other / "static-contract-protocol-2026-09-30-003/test_p0.jsonl", "static"),
        cohort_record(other / "maneuver-contract-protocol-2026-09-30-003/test_p0.jsonl", "maneuver"),
    ]
    attempt = json.loads(args.nl2spec_attempt.read_text())
    (output / "nl2spec_native_attempt.json").write_text(json.dumps(attempt, indent=2) + "\n")
    result = {
        "status": "ORIGINAL_METHOD_CHECKS_EXECUTED_COMMON_TASK_COMPARISON_BLOCKED",
        "common_task_predictions": 0,
        "external_performance_metrics": None,
        "input_information_audit": cohorts,
        "nl2spec": {
            "status": "NATIVE_CLI_DEMO_EXECUTED" if attempt.get("exit_code") == 0 else "NATIVE_CLI_ATTEMPT_FAILED",
            "output_type": "LTL and subtranslation confidence, not a candidate label",
            "interactive_correction_executed": False,
        },
        "NL2TL": nl2tl_demo(args, output),
        "DriveLM": {
            "status": "NATIVE_INFERENCE_NOT_EXECUTED",
            "resource_blocker": "Original LLaMA-7B consolidated weights not found in inspected local cache/runtime/data/third_party roots",
            "scope": "Released challenge baseline is LLaMA-Adapter V2; do not equate it with a reproduced full DriveLM-Agent",
            "task_blocker": "Official Graph VQA inputs and metrics differ from our numeric candidate benchmark",
        },
        "DriveVLM": {
            "status": "NATIVE_INFERENCE_NOT_EXECUTED",
            "resource_blocker": "Official repository has only github-pages branch with HTML, images and paper; no inference implementation or checkpoints in inspected source",
            "task_blocker": "Native scene analysis and hierarchical planning are not our candidate-label task",
        },
        "conclusion": "No common-task comparison is reported. Native translation demos establish execution only. A scoreable adaptation would change the original methods and is prohibited by this protocol.",
    }
    (output / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "status": result["status"], "nl2tl": result["NL2TL"]}))


if __name__ == "__main__":
    main()
