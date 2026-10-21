# GuardSynth coauthor seminar

## Overview slides

[problem-definition-v02-en.tex](problem-definition-v02-en.tex) and its
[PDF](problem-definition-v02-en.pdf) are a twelve-slide redesign of the v01 deck
below, created on 2026-10-20. They use the manuscript terminology in short keyword
form and follow the order problem definition, approach, results, contributions:

1. Title: NCA manuscript title, authors, and affiliations.
2. Problem: the same pedestrian-entry scene under two waiting rules; constraint
   compliance versus preferred selection.
3. Problem definition: the three construction problems from the Introduction.
4. Approach: the four-stage workflow (construction, EBLC, SMT checking, CNL).
5. Approach example: evidence binding, EBLC restriction, counterexample query, CNL.
6. Results setup: tasks, compared conditions, and PSS/CVR/RPA.
7. Fresh-adapter CVR/RPA/PSS with identical CNL at evaluation (Results 5.1).
8. Semantic-loss and pretrained-8B controls (Results 5.1, 5.2).
9. Six-task P0/P1/P2 PSS/CVR and RPA (Results 5.4, 5.5).
10. Fault injection: 288/288 detected, 48/48 accepted, 0/48 jointly wrong (Results 5.9).
11. Composition: 58 of 176 UNSAT, 12 three-way conflicts (Results 5.10).
12. Contributions and scope.

All numbers are reused from the NCA Results; there are no new
experiments. The design uses a dark title slide, TeX Gyre Adventor headings, and
native TikZ graphics. Build it the same way as v01, substituting the filename. v01 is
unchanged.

## Problem-definition slides

The English [source](problem-definition-v01-en.tex) and
[PDF](problem-definition-v01-en.pdf) contain sixteen slides, updated on
2026-10-20 against the active NCA Introduction
[01-introduction-v03-en.tex](../neural-computing-applications/01-introduction-v03-en.tex),
Method, Results, and the
[terminology authority](../neural-computing-applications/BEHAVIORAL_CONSTRAINT_TERMINOLOGY_NOTES_V01.md).

1. Technology gaps: rule use, interacting conditions, and formal/language meaning.
2. The focused study: candidate selection and checkable constraint construction.
3. Three construction problems from the Introduction: evidence/applicability,
   logical meaning/composition, and specification--sentence correspondence.
4. The matching EBLC/SMT/CNL approach, with behavior assessed separately.
5. Why constraints need checking: Uber suppression timing, Cruise behavior
   transitions, and the Rule 129 exception, placed immediately after the approach.
   These are motivation, not proof of accident prevention.
6. Admissibility, the supplied synthetic objective J, and CE training of the
   preferred candidate's label. SMT does not optimize J.
7. Pedestrian-entry evidence, specification, logical gate, and generated CNL.
8. Experimental setup only, including PSS/CVR/RPA definitions and common-rule inputs.
9. Fresh-adapter constraint violation rate and rule-pair accuracy charts.
10. Semantic-loss and pretrained-8B controls with the same evaluation rule.
11. Learning-specification fault detection and jointly wrong evidence--specification controls.
12. Documented suppression branch + authored motion model + stopping objective:
    each pair SAT, all three UNSAT; a hypothetical compatibility case, not Tempe reconstruction.
13. FHWA-informed yellow dilemma-zone example under explicit nominal braking
    and stop/proceed assumptions.
14. Waymo autonomous-driving interlocks and restricted Rule 129 exception preservation.
15. Document-grounded composition results: 176 configurations, 118 SAT / 58 UNSAT,
    including 12 requiring joint three-group checks; 896 queries / 832 validated SAT witnesses.
16. The separate evidence for learning benefits, fault detection, and composition checking.

The earlier two shuffled-association slides are removed, matching their removal
from the manuscript. Preferred-selection score (PSS) replaces unqualified
accuracy; constraint violation rate (CVR) and rule-pair accuracy (RPA) remain
distinct. Rates concern supplied candidates and a synthetic objective, not
general driving quality. Source/evidence records are not treated as independent
truth. Evidence/sentence checks and added logic--rule probes are post-training;
the composition diagnostic does not generate learning inputs or test VLM behavior.
All new case slides provide a short interpretation below their tables or diagrams.

Result sources (also identified by manuscript section on slides):

- [Fresh-adapter and pretrained-model analysis](../../artifacts/public/paper1-vlm-constraint-baselines-001/vlm-constraint-baseline-analysis-2026-10-12-001/RESULT.json).
- [Archived 8B predictions](../../artifacts/public/paper1-vlm-constraint-baselines-001/vlm-constraint-baselines-2026-10-12-001/pretrained_8b/predictions.jsonl): entry RPA is 1/120 = 0.83%; no 12-token cap hits in the 240 entry rows.
- [Learning-specification fault injection](../../artifacts/public/paper1-learning-specification-faults-001/learning-specification-faults-2026-10-12-001/RESULT.json).
- [Document-grounded composition results](../../artifacts/public/paper1-constraint-composition-001/document-grounded-composition-2026-10-17-002/RESULT.json),
  [official-source catalog](../../artifacts/public/paper1-constraint-composition-001/document-grounded-composition-2026-10-17-002/SOURCE_CATALOG.json), and
  [source review / natural-formal tables](../../artifacts/public/paper1-constraint-composition-001/document-grounded-composition-2026-10-17-002/REPORT_KO.md).
  The numerical states, requests, objectives, and motion assumptions are authored;
  documented clauses are manually formalized. The counts are not frequencies of
  real policy conflicts. Emergency-trigger eligibility, jerk, full legal texts,
  real-scene truth, and operational safety are outside the executed model.

The existing white background, thin outlined boxes, native TikZ diagrams, and
PGFPlots charts are retained. There are no new experiments, predictions, copied
result packages, or raster figure assets. Build twice with the XeLaTeX command
below, substituting the English filename. PDFs and compiler output stay beside
their sources under the paper-build colocation rule.

[problem-definition-v01-ko.tex](problem-definition-v01-ko.tex) is a separate
two-slide Korean deck based on the NCA Introduction v02. It covers
rule-dependent action selection and the accuracy of learning constraints.
It contains no proposed-method pipeline, experiment results, or contribution
slides. The waiting-time example is illustrative, not a legal requirement.

Build with XeLaTeX twice from this directory. On this machine, use the existing
TeX support path:

    TEXINPUTS=:/tmp/guardsynth-seminar-texdeps/tex// xelatex -interaction=nonstopmode -halt-on-error problem-definition-v01-ko.tex

The working [PDF](problem-definition-v01-ko.pdf) and compiler files stay beside
the source under the repository's paper-build colocation rule. The earlier
seminar and its archived runs below are unchanged.

- Owner: `guardsynth-coc`
- Audience: manuscript coauthors
- Language and format: English, 16:9 LaTeX Beamer; the earlier Korean edition is retained
- English source: [coauthor-seminar-v01-en.tex](coauthor-seminar-v01-en.tex)
- Earlier Korean source: [coauthor-seminar-v01-ko.tex](coauthor-seminar-v01-ko.tex)
- English duration: 29 main slides, 27-minute presentation and 3-minute discussion; 9 optional backup slides. The Korean edition has 24 main slides.
- Presenter notes: each frame contains English (or Korean in the earlier edition) `\note{...}` text with suggested timing. The build creates a separate notes PDF.

The seminar follows the maintained [English manuscript](../ieee-access/main.tex) and [experimental supplement](../ieee-access/IEEE_ACCESS_EXPERIMENTS_SUPPLEMENT_V01_EN.md). Tables and the contract-pair plot reproduce existing results. Method diagrams and examples are seminar illustrations; they are not new observations or experiments. The deck distinguishes supplied rule values, assumptions, logical feasibility, learned action selection, and the limits of synthetic evaluation.

## Build

From the repository root:

```bash
python3 projects/04-guardsynth-coc/paper/seminar/build_seminar.py --language en --run-id coauthor-seminar-2026-10-08-001
```

XeLaTeX, Beamer, fontspec, TikZ/PGFPlots, and the installed `TeX Gyre Heros` and `Latin Modern Mono` fonts are required for English. The Korean edition requires `Noto Sans CJK KR` and `Noto Sans Mono CJK KR`. Completed runs are preserved. For a subsequent revision, provide a new run ID, for example `--run-id coauthor-seminar-2026-10-07-008`. Select `--language ko` for the earlier Korean source. Build logs, input hashes, the 30-minute schedule, slide PDF, and presenter-notes PDF are stored under `projects/04-guardsynth-coc/artifacts/public/paper1-seminar-001/<run-id>/`.

Current English output: [slides PDF](../../artifacts/public/paper1-seminar-001/coauthor-seminar-2026-10-08-001/coauthor-seminar-v01-en.pdf) and [presenter notes PDF](../../artifacts/public/paper1-seminar-001/coauthor-seminar-2026-10-08-001/coauthor-seminar-v01-en-notes.pdf).

The current machine lacks system-wide PGF/PGFPlots. The first build uses the already available TeX libraries copied into `/tmp/guardsynth-seminar-texdeps/tex/` and invokes the script with `TEXINPUTS=:/tmp/guardsynth-seminar-texdeps/tex//`. This temporary support is recorded in the run manifest; a standard TeX installation containing PGF/PGFPlots needs no path override. The generated PDFs need no TeX dependencies to view.

## Suggested pacing

| Main slides | Content | Minutes |
|---|---|---:|
| 1–4 | Introduction: context, problem, approach, contribution | 3.5 |
| 5–6 | Related work and comparison | 2 |
| 7–15 | Approach: constraint types/sources, EBLC, checks and results, CNL | 9 |
| 16–26 | Experiments: comparators, datasets, comparison graphs, additional evaluations, limitations | 11 |
| 27–28 | Conclusion and takeaway | 1.5 |
| 29 | Coauthor discussion | 3 |

Backup slides cover task fields, all six queries, specification mistakes, lifecycle policy, detailed training settings, exact primary result values, unseen numerical values, additional evaluation settings/counting units, and external-method execution availability. They are outside the 30-minute schedule.


## Comparisons with existing research

English slides 5–6 compare central objectives and representations of DriveLM, DriveVLM, Alpamayo-R1, Drive-R1, DriveReg, Esterle et al., NL2TL, nl2spec, ACE, and our preceding Safety-Constrained CoC manuscript. Paper names link to primary sources checked on 2026-10-07. The comparison is methodological positioning, not an exhaustive feature audit or a numerical ranking: those external systems were not evaluated on our benchmark. The preceding manuscript already contributes natural-language guards and paired-contract tasks; P2 adds the traceable EBLC development path.

## Presentation structure

The five sections follow context/problem/approach/contribution, related work, constraint development and verification, experimental comparison, and conclusion. Short bullets, tables, and diagrams replace extended prose. Slide 14 adds the layer-specific specification-error results. Slides 19–22 show primary accuracy/violations, reasoning-prompt controls, contract-pair accuracy, and constraint-association shuffling. Slides 23–25 add representation variants, paraphrase/hard conditions, and visual-input diagnostics, with settings and scope in their English presenter notes. Backup B7 reports unseen numerical values; B8 distinguishes rows, predictions, semantic groups, and specification cases.

Slide 17 states that direct performance comparisons against nl2spec, NL2TL, DriveLM, and DriveVLM were not conducted, explaining the task/output differences and unavailable execution resources. It separately introduces the measured Zero-Shot CoT/basic Plan-and-Solve prompting adaptations on existing P0 checkpoints, whose results appear on slide 20. Backup B9 retains the original-example execution and availability records without comparative performance claims. These prompting controls are not reproductions of the original methods' benchmarks. This slide revision reuses archived results and creates no new model predictions.

Slides 17 and 20 explicitly define the graph labels: `P0 + ZS-CoT` adds Zero-Shot Chain-of-Thought prompting, while `P0 + PS` adds basic Plan-and-Solve prompting to the same existing P0 checkpoints at inference. The plus sign does not denote retraining or additional constraint information. The notes describe answer extraction and the unequal reasoning token caps.
