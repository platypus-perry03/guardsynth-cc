# GuardSynth-CC Project Structure Codex

- Codex version: `v4.1`
- Effective date: `2026-10-09`
- Authority: repository-wide file placement and ownership
- Machine registry: [`PROJECT_REGISTRY.json`](../../PROJECT_REGISTRY.json)
- Agent entry point: [`AGENTS.md`](../../AGENTS.md)
- Naming authority: [`FILE_NAMING_CODEX.md`](FILE_NAMING_CODEX.md)

## 1. Governing idea

The repository is a monorepo of five research projects and one shared verification platform.
The unit of ownership is a research question, not a file type and not a paper number.

| Owner ID | Research responsibility |
|---|---|
| `safety-constrained-coc` | Does a supplied execution constraint improve goal-preserving VLM behavior? |
| `specification-alignment` | How do natural-language, structured, and executable specification interfaces differ? |
| `sequential-coc-verification` | Are sequential CoC annotations statefully and temporally consistent? |
| `guardsynth-coc` | Can CoC, scene, rule, provenance, and assurance inputs synthesize applicable constraints? |
| `eblc-language-verification` | Does EBLC provide traceable lifecycle semantics and verifiable multi-target lowering beyond simpler contract representations? |
| `eblc-bcv` | Shared EBLC language, Core lowering, runtime monitor, BCV, and SMT tooling |

EBLC is not the final GuardSynth research objective. Its reusable implementation remains a
platform consumed by GuardSynth, specification-alignment, and the independent EBLC language
verification research project. Project 05 owns the independent research question, evaluation,
and paper; it does not duplicate or absorb the platform implementation.

## 2. Canonical tree

```text
guardsynth-cc/
├── projects/
│   ├── 01-safety-constrained-coc/
│   ├── 02-specification-alignment/
│   ├── 03-sequential-coc-verification/
│   ├── 04-guardsynth-coc/        # source, docs, paper, artifacts together
│   └── 05-eblc-language-verification/
├── platforms/
│   └── eblc-bcv/
├── shared/
├── apps/
│   └── research_portal/
├── data/                        # shared source data, separated by license
├── governance/
│   ├── superpowers/
│   └── worktrees/
├── archive/
│   └── agent-history/superpowers/
├── cli/                         # repository-wide compatibility and maintenance entry points
├── runtime/
├── third_party/
└── tests/structure/             # repository-wide policy tests only
```

### 2.1 Root namespace contract

Every root directory has one explicit role. A directory not listed here requires a Codex
decision before creation.

| Root | Allowed content | Forbidden content |
|---|---|---|
| `projects/` | one complete tree per research question | generic shared utilities |
| `platforms/` | reusable language/verification platforms | scene- or paper-specific logic |
| `apps/` | maintained web/desktop applications and their tests | experiment run output |
| `shared/` | code/schema with at least two real owners | speculative abstractions |
| `governance/` | repository policies and operating procedures | project research plans |
| `docs/` | repository architecture and migration records | project plans/reports/surveys |
| `data/` | license-separated shared inputs plus ownership catalog | generated reports |
| `runtime/` | installed solvers, environments, runtime catalog | maintained project source |
| `third_party/` | pinned upstream checkouts and ownership catalog | locally authored project code |
| `archive/` | immutable superseded/imported history | active plans or implementation |
| `cli/` | repository maintenance tools and temporary CLI shims | new domain pipelines |
| `src/` | temporary import shims only | new implementation |
| `experiments/` | temporary import shims only | new protocols or analyses |
| `tests/` | repository structure/governance tests only | project/platform behavior tests |
| `.superpowers/` | ignored disposable agent scratch | canonical documentation |
| `.worktrees/` | `README.md` and `registry.json` only | actual Git worktrees |
| `.agents/`, `.codex/`, `.aws/` | ignored local tool configuration | research artifacts |

Generated caches such as `.pytest_cache/` and `.ruff_cache/` are ignored operational state and
are not project namespaces. `.git/` is Git-owned metadata.

Shared infrastructure is not ownerless. `data/`, `runtime/`, and `third_party/` each carry an
`OWNERSHIP.json` catalog that records which project/platform consumes every immediate child.

## 3. Standard project contract

Every `projects/<NN>-<project-id>/` has the following contract. `NN` is display and workflow
order; the stable logical owner remains the unnumbered `project_id` in `PROJECT.yaml` and
`PROJECT_REGISTRY.json`.

```text
README.md              human entry point and claim boundary
PROJECT.yaml           ownership, dependencies, canonical documents, artifact root
STATUS.md              current state, blocker, and next work only
docs/
  charter/             stable research question and non-goals
  requirements/        work-package inputs, outputs, tests, claim boundary
  plans/
    01_RESEARCH_PLAN_VNN.md      governing research scope and success criteria
    02_PROJECT_MILESTONES.md     ordered decomposition and evidence gates
    03_PROJECT_EXECUTION_TRACKER.md  current work and blockers
  designs/             interfaces, semantics, and experiment designs
  decisions/           alternatives and irreversible scope decisions
  reports/             curated multi-run reports, not raw runs
  surveys/
    README.md           authority/status index and relationship to the governing plan
    ...                 related-work inputs, novelty/method studies, and research notes
src/                   maintained project-specific implementation
pipelines/             project-specific user workflows
tests/                 unit, integration, and acceptance tests
experiments/           protocols, configs, fixtures, experiment-local analysis
paper/                 manuscript, working PDF, build files, figures, submission assets
artifacts/
  RESULT_INDEX.md       single result entry point, beside the generated output
  public/              shareable results
  restricted/          licensed/private results, ignored by Git
  intermediate/        current regenerable build or pipeline output
```

Do not create a project file before choosing exactly one project owner. A file needed by two
projects is not automatically shared: keep it with the first real owner until a second real
consumer justifies promotion.

Every registered research project uses the same controlled planning set. The research plan is
the authority for scope and success criteria, the milestone ledger refines that plan, and the
execution tracker selects current work under both. `README.md`, `STATUS.md`, and `PROJECT.yaml`
must link to this set. Related-work surveys are formal inputs to research planning. Survey
documents remain in `docs/surveys/`; their `README.md` records authority status, upstream input,
and the planning or method decision each item informs. A current canonical survey is linked by
the research plan. Independent surveys are not assigned a false hierarchy merely for sorting;
only a real related-work-to-analysis-to-method-to-strategy refinement set receives local
two-digit prefixes. The File Naming Codex defines roles, metadata, versions, and exclusions.

## 4. Shared platform contract

`platforms/eblc-bcv/` owns reusable EBLC representations and operational semantics, typed
derivation and composition, Core lowering, runtime monitoring, BCV mutation workflows, and
SMT/Z3 compilation. It has its own `PLATFORM.yaml`, specifications, release notes, tests, and
artifact namespace. GuardSynth source retrieval, scene grounding, and applicability logic are
forbidden here. `projects/05-eblc-language-verification/` may evaluate and publish the platform,
but paper-specific protocols, baselines, analyses, and manuscripts belong to that project while
reusable code and conformance tests remain in the platform.

## 5. Document placement decision

Use this order:

1. Is it a paper source, compilation output, or submission asset? Keep it in the
   owning project's corresponding `paper/` directory.
2. Is it an immutable experiment run output? Put it under the owner's artifact namespace.
3. Is it a requirement, plan, design, decision, report, or survey for one research question?
   Put it in that project's corresponding `docs/` directory.
4. Is it repository architecture or governance? Put it in root `docs/architecture/` or
   `governance/`.
5. Is it temporary agent work? Keep it in ignored `.superpowers/` or `/tmp`; do not promote it.

The repository root, `docs/`, and `experiments/` are not general-purpose dumping grounds.

## 6. Results, consolidation, and retention

New runs use:

```text
projects/<NN>-<project-id>/artifacts/<class>/<experiment-id>/<run-id>/
platforms/<platform-id>/artifacts/<class>/<experiment-id>/<run-id>/
```

`<class>` is `public`, `restricted`, or `intermediate`. Final runs contain
`RUN_MANIFEST.json`, `RESULT.json`, and a scoped report when required. Runners must refuse to
overwrite an existing run ID.

New run manifests declare a stable `task_id`, completion status, creation time, and concrete
`inputs` paths. Those fields make task identity and retention dependencies explicit; a date
or modification time alone is insufficient. Existing migrated runs keep their recorded metadata
and use the migration catalog for missing task/retention information.

The registry's `artifact_root` is authoritative. Applications write into their registered
project owner's artifact root. Root `artifacts/` and owner-local `results/` are retired; do
not recreate them, keep compatibility symlinks, or create another output tree.

One task has one experiment directory within its owner and classification. Merge legacy and
current locations into that directory. Public aggregates and restricted evidence remain
separate because their access restrictions differ. Use `artifacts/RESULT_INDEX.md` as the
owner's only result index. Maintained source belongs in `src/`, `experiments/`, or `paper/`.
Experiment PDFs, logs, and exports belong in artifacts; paper compilation follows section 6.1.

Keep the latest completed result for each actual task, not merely the last directory in an
experiment. A protocol, training run, evaluation, and figure can be distinct tasks. Independent
seeds, conditions, cohorts, and environments are not interchangeable versions. An incomplete
newer execution does not replace a completed result. Preserve active workspace changes.

Before removing superseded results, follow concrete input references transitively from retained
results, current papers, and maintained consumers. Retain those inputs, including older ones.
Historical mentions alone do not pin an obsolete run. Remove unreferenced superseded runs,
failed retries replaced by a completed execution, disposable build caches, and verified exact
duplicates. Select one canonical deliverable, redirect its consumers, and then remove redundant
copies; required run metadata is exempt from file-level deduplication. Never replace a cited
old measurement with a newer different measurement just to make a link resolve.

Record relocation, deleted runs, superseding results, retention reasons, and duplicate-file
redirects in `docs/architecture/ARTIFACT_MIGRATION.json`. Preserve research values and raw review
submissions. If relocation requires an embedded path update, record its original digest and
refresh affected generated-file checksums explicitly. This approved v4 migration supersedes
the old policy of retaining every v2/v3 run indefinitely.

### 6.1 Paper builds

Decision `PAPER-BUILD-COLOCATION-2026-10-09` applies to all maintained manuscripts.
Keep the working PDF, `.aux`, `.out`, `.bbl`, `.blg`, and `.log` beside that manuscript's
`main.tex` and Makefile in `projects/<NN>-<project-id>/paper/<manuscript>/`. Splitting a
manuscript and its compilation output creates two locations for one editing task.
Paper builds therefore do not use `artifacts/intermediate/`, dated experiment/run
directories, or experiment `RUN_MANIFEST.json` / `RESULT.json` requirements.

Rebuilding replaces the same manuscript's generated files. Keep compiler caches local
and ignored; auxiliary files remain ignored by Git, while the working PDF may be tracked.
The owner result index links to the paper directory and its PDF without copying them.
Experiment evidence and reusable experiment figures retain their artifact ownership;
paper compilation does not duplicate their source data. Record paper-build relocations
under `paper_builds` in the artifact migration catalog, separately from experiment runs.

## 7. Compatibility roots

Legacy root packages and CLI namespaces may remain only as small forwarding shims during the
v3 transition. A shim must contain no domain logic and must name its canonical owner. New code
must import or execute the canonical project/platform location.

## 8. Superpowers artifact policy

Superpowers may create unlimited scratch material only under ignored `.superpowers/`.
Canonical promotion is limited to one final, human-reviewed document per required document
class and must be registered in `governance/superpowers/PROMOTIONS.json`. Task briefs, review
diffs, snapshots, hashes, and intermediate review packages are never promoted. See
[`governance/superpowers/README.md`](../../governance/superpowers/README.md).

## 9. Worktree policy

Worktrees are operational state, not project content. Actual Git worktrees live outside the
repository at `../guardsynth-cc-worktrees/<work-id>/`. Root `.worktrees/` contains only its
tracked policy README and registry. See
[`governance/worktrees/README.md`](../../governance/worktrees/README.md).

## 10. Enforcement

`tests/structure/test_project_layout.py` verifies project roots, registry ownership, forbidden
new legacy content, Superpowers separation, worktree policy, portal ownership, and canonical
links. `cli/checks/file_naming.py` audits maintained filenames. Any structural exception
requires a decision record and a Codex version update.
