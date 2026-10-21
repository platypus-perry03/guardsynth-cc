# GuardSynth-CC research monorepo

This repository contains related but distinct research projects about Chain-of-Causation
(CoC), constraint-conditioned driving, sequential verification, and evidence-grounded contract
synthesis. EBLC/BCV is the shared executable-contract platform used by those projects.

## Start here

- [Research project index](PROJECTS.md)
- [Project Structure Codex v4](docs/architecture/PROJECT_STRUCTURE_CODEX.md)
- [Research document naming and hierarchy](docs/architecture/FILE_NAMING_CODEX.md)
- [Machine-readable project registry](PROJECT_REGISTRY.json)
- [GuardSynth-CoC status](projects/04-guardsynth-coc/STATUS.md)
- [EBLC language-verification research status](projects/05-eblc-language-verification/STATUS.md)
- [Research and review portal](apps/research_portal/README.md)

## Owner-oriented layout

```text
projects/      five owners, each with docs/code/tests/experiments/paper/artifacts
platforms/     reusable EBLC/BCV implementation and its own artifacts
apps/          repository applications
shared/        genuinely cross-owner utilities
governance/    Superpowers and worktree policies
docs/          repository architecture only
data/          license-separated shared inputs
runtime/       pinned local execution environments and solvers
third_party/   pinned upstream checkouts
archive/       immutable historical material
```

Root `src/`, `experiments/`, and domain CLI namespaces are compatibility shims only. New domain
content must be placed under its project or platform. Root `tests/` contains repository-policy
tests only.

## Reproducibility and restricted data

- Runs use `projects/<NN>-<project-id>/artifacts/<class>/...` or
  `platforms/<platform-id>/artifacts/<class>/...`.
- Paper sources, working PDFs, and compiler auxiliary files are managed together in
  the corresponding `paper/` directory; paper builds do not use intermediate artifacts.
- Each owner has one `artifacts/RESULT_INDEX.md`; root artifacts and separate results
  trees are retired. Keep the latest completed task result and required inputs.
- [Artifact migration and retention catalog](docs/architecture/ARTIFACT_MIGRATION.json)
  records merged locations, removed runs, and duplicate redirects.
- Restricted NVIDIA-derived data and outputs must remain in restricted namespaces.
- Actual-vehicle validation is deferred until the research, paper, and patent stages described
  by the GuardSynth project decision records.

The exact public-manifest exclusion policy is implemented in
[`cli/checks/build_manifest.py`](cli/checks/build_manifest.py).

## GuardSynth NCA reproducibility package

The [sanitized NCA reproducibility distribution](projects/04-guardsynth-coc/artifacts/public/paper1-reproducibility-release-001/github-release-2026-10-21-002/README.md) provides selected code (MIT), synthetic data and generated records (CC BY 4.0), with metric verification and formal-check reproduction instructions. These licenses apply to that distribution, not the whole monorepo. Model weights, restricted road imagery and credentials are excluded.
