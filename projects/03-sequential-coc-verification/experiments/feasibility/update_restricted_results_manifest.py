#!/usr/bin/env python3
"""Regenerate the integrity manifest for access-controlled experiment results."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "PROJECT_REGISTRY.json").is_file())
sys.path.insert(0, str(ROOT))
from cli.project_paths import artifact_roots


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    for results in artifact_roots(ROOT, "restricted"):
        manifest = results / "manifest.sha256"
        files = sorted(path for path in results.rglob("*") if path.is_file() and path != manifest)
        lines = [f"{sha256(path)}  ./{path.relative_to(results).as_posix()}" for path in files]
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest.chmod(0o600)
        print(f"updated {manifest.relative_to(ROOT)} with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
