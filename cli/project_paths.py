"""Stable repository paths for CLI entry points.

Pipeline modules may be regrouped by domain without changing their root
calculation.  A missing marker fails closed instead of silently selecting a
parent directory.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json


def artifact_digest_matches(path: str | Path, expected: str) -> bool:
    """Accept current bytes or an explicitly recorded relocation of those bytes."""
    path = Path(path).resolve()
    with path.open("rb") as stream:
        current = hashlib.file_digest(stream, "sha256").hexdigest()
    if current == expected:
        return True
    root = project_root(__file__)
    if not path.is_relative_to(root):
        return False
    catalog = json.loads((root / "docs/architecture/ARTIFACT_MIGRATION.json").read_text())
    relative = path.relative_to(root).as_posix()
    return any(
        entry["path"] == relative
        and entry["before_sha256"] == expected
        and entry["after_sha256"] == current
        for entry in catalog["rewritten_files"]
    )


def artifact_roots(root: str | Path, classification: str) -> tuple[Path, ...]:
    root = Path(root)
    registry = json.loads((root / "PROJECT_REGISTRY.json").read_text(encoding="utf-8"))
    return tuple(
        (root / entry["artifact_root"] / classification).resolve()
        for entry in (*registry["projects"], *registry["platforms"])
    )


def project_root(start: str | Path) -> Path:
    candidate = Path(start).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (
            (directory / "PROJECT_STRUCTURE.md").is_file()
            and (directory / "src").is_dir()
            and (directory / "cli").is_dir()
        ):
            return directory
    raise RuntimeError(f"project root markers not found from {start}")
