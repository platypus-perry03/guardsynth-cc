"""Build a coauthor seminar and a separate presenter-notes PDF."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[4]
PAPER = ROOT / "projects/04-guardsynth-coc/paper/ieee-access"
ARTIFACTS = ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-seminar-001"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "ko"), default="en")
    parser.add_argument("--run-id", default="coauthor-seminar-2026-10-07-007")
    args = parser.parse_args()
    source_path = Path(__file__).with_name(f"coauthor-seminar-v01-{args.language}.tex")
    if not re.fullmatch(r"coauthor-seminar-\d{4}-\d{2}-\d{2}-\d{3}", args.run_id):
        parser.error("Use coauthor-seminar-YYYY-MM-DD-NNN as the run ID")
    out = ARTIFACTS / args.run_id
    if (out / "RESULT.json").exists():
        parser.error("Completed seminar runs are immutable; choose a new --run-id")
    engine = shutil.which("xelatex")
    if engine is None:
        parser.error("XeLaTeX is required")
    source = source_path.read_text()
    main_part, backup_part = source.split(r"\appendix", 1)
    main_frames = main_part.count(r"\begin{frame}")
    backup_frames = backup_part.count(r"\begin{frame}")
    timings = re.findall(r"^% TIMING (\d+) ([\d.]+)$", source, re.M)
    assert main_frames == len(timings) == (29 if args.language == "en" else 24)
    assert backup_frames == (9 if args.language == "en" else 6)
    assert source.count(r"\note{") == main_frames + backup_frames
    elapsed = 0
    agenda = []
    for slide, minutes in timings:
        seconds = round(float(minutes) * 60)
        agenda.append({"slide": int(slide), "start_seconds": elapsed, "duration_seconds": seconds})
        elapsed += seconds
    assert elapsed == 1800
    assert sum(row["duration_seconds"] for row in agenda[:-1]) == 1620
    inputs = [
        source_path,
        PAPER / "main.tex",
        PAPER / "references.bib",
        PAPER / "IEEE_ACCESS_METHODOLOGY_V01_EN.md",
        PAPER / "IEEE_ACCESS_EXPERIMENTS_V01_EN.md",
        PAPER / "IEEE_ACCESS_EXPERIMENTS_SUPPLEMENT_V01_EN.md",
        PAPER / "IEEE_ACCESS_RELATED_WORK_V01_EN.md",
    ]
    if args.language == "en":
        inputs.extend([
            ROOT / "projects/04-guardsynth-coc/paper/ieee-access/figures/reasoning-comparison-en.pdf",
            ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001/temporal-expansion-learning-2026-09-29-001/RESULT.json",
            ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-temporal-diversity-001/expanded-diagnostics-analysis-2026-09-30-001/RESULT.json",
            ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-reasoning-comparison-001/reasoning-comparison-2026-10-07-001/RESULT.json",
        ])
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    out.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for mode, job in [("slides", source_path.stem), ("notes", source_path.stem + "-notes")]:
        tex_input = str(source_path)
        if mode == "notes":
            tex_input = r"\def\seminarnotes{1}\input{" + str(source_path) + "}"
        for attempt in (1, 2):
            command = [engine, "-interaction=nonstopmode", "-halt-on-error", f"-jobname={job}", tex_input]
            result = subprocess.run(command, cwd=out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (out / f"build-{mode}-{attempt}.log").write_text(result.stdout)
            assert result.returncode == 0, result.stdout[-6000:]
        log = (out / (job + ".log")).read_text()
        assert not re.search(r"Overfull|Missing character|LaTeX Warning:.*undefined|multiply defined", log, re.I), mode
        pages = int(re.search(r"Output written on .*?\((\d+) pages?", log, re.S)[1])
        assert pages == main_frames + backup_frames, (mode, pages)
        outputs[mode] = {"file": job + ".pdf", "pages": pages, "sha256": sha(out / (job + ".pdf"))}
    assert before == {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    manifest = {
        "project_id": "guardsynth-coc",
        "run_id": args.run_id,
        "source": str(source_path.relative_to(ROOT)),
        "language": args.language,
        "input_sha256": before,
        "outputs": outputs,
        "engine": engine,
        "texinputs": os.environ.get("TEXINPUTS", "system defaults"),
        "main_slides": main_frames,
        "backup_slides": backup_frames,
        "talk_minutes": 27,
        "discussion_minutes": 3,
        "timing": agenda,
        "manuscript_and_experiments_modified": False,
        "new_model_predictions": 0,
        "visual_review": "Pending before finalizing RESULT.json",
    }
    (out / "RUN_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"build": "PASS", "output": str(out), "main_slides": main_frames,
                      "backup_slides": backup_frames, "duration_minutes": elapsed / 60,
                      "outputs": outputs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
