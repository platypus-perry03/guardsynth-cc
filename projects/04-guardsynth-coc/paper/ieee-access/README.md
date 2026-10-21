# GuardSynth: Augmenting Chain-of-Causation with Verified Behavioral Constraints for Autonomous Driving

Current English author revision: 2026-10-08, verified final Introduction following R01–R42. The maintained English source, PDF, bibliography, template, and build files are together in this `paper/ieee-access/` directory; the frozen predecessor is `manuscript-revision-2026-09-30-001`. Korean PDFs retain their previous revision. The English experimental supplement now includes S11 (aggregate Alpamayo-R1 diagnostics) and S12 (position-hold candidate-selection training). Restricted raw media and model outputs are not included.

R41 strengthens the comparison with nl2spec, NL2TL, DriveLM, and DriveVLM, and records the native execution checks in Table 2. Experimental setup explains task and resource limits on direct comparison. Results Section VI.B reports the two supplementary reasoning-prompt controls; Figure 5 renders their archived results at manuscript width. These controls reuse P0 checkpoints without adding constraints. The native execution checks are not common-task performance results, and the reasoning controls are not full reproductions of the original papers.

The author-approved batch reorganizes the method into constraint extraction and evidence binding, EBLC specification, logical verification, and CNL/CoC augmentation. It clarifies query properties and their limits, human review, candidate scores and reference labels, and implementation provenance. Label rotation and reference construction are explained in the experimental setup. The duplicate temporal-boundary figure is omitted; automatic table and figure references follow the new order. The second batch clarifies dataset generation and splits, adds the dataset-size table, separates model evaluation from auxiliary SMT agreement checks, and connects result explanations to labeled tables and figures. Discussion, conclusion, numerical results, and experiment records are unchanged; the Introduction was subsequently replaced with the verified author-supplied draft on 2026-10-08. [Revision notes](IEEE_ACCESS_MANUSCRIPT_REVISION_NOTES_V01_KO.md) record completed items and old-to-current figure/table mappings.

| Document | Korean | English |
|---|---|---|
| Integrated manuscript | [PDF](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/ieee-access-manuscript-ko.pdf) | [IEEE Access PDF](ieee-access-manuscript-en.pdf) |
| Detailed experiments | [Source](IEEE_ACCESS_EXPERIMENTS_SUPPLEMENT_V01_KO.md) · [PDF](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/ieee-access-experiments-supplement-v01-ko.pdf) | [Source](IEEE_ACCESS_EXPERIMENTS_SUPPLEMENT_V01_EN.md) · [PDF](../../artifacts/public/paper1-introduction-revision-001/introduction-revision-2026-10-08-001/ieee-access-experiments-supplement-v01-en.pdf) |
| Methodology | [Source](IEEE_ACCESS_METHODOLOGY_V01_KO.md) | [Source](IEEE_ACCESS_METHODOLOGY_V01_EN.md) |
| Experimental main text | [Source](IEEE_ACCESS_EXPERIMENTS_V01_KO.md) | [Source](IEEE_ACCESS_EXPERIMENTS_V01_EN.md) |
| Discussion | [Source](IEEE_ACCESS_DISCUSSION_V01_KO.md) | [Source](IEEE_ACCESS_DISCUSSION_V01_EN.md) |

The section Markdown files are the editable authoring sources. The 20 references are maintained in [references.bib](references.bib); existing keys `r1`–`r15` are retained, `r16`–`r17` identify Zero-shot CoT and Plan-and-Solve, and `r18`–`r20` identify Drive the Thoughts, context-conditioned HJ reachability, and the Alpamayo 1.5 model card. Citation numbers follow BibTeX's order of first citation. The English manuscript uses the pinned IEEEtran BibTeX style in [ieee-access-template](template/README.md). Edit the `.bib` database rather than generated `.bbl` files. `main.tex` is the synchronized English integration entry point; it no longer contains the historical temporal-only draft. [Build snapshot](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/build_manuscript.py) and [source manifest](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/RUN_MANIFEST.json) record inputs. English uses the official IEEE Access template; Korean is a two-column author-review edition.

The [Introduction source](IEEE_ACCESS_INTRODUCTION_V01_EN.md) separates reasoning–trajectory agreement from compliance with supplied restrictions and distinguishes inference-only diagnostics from training interventions. Its two footnotes refer to supplementary sections S11 and S12. The updated English supplement preserves frozen S1–S10 and adds aggregate protocols and results; individual licensed images, trajectories, and full CoC outputs remain restricted.

## Contribution and terminology

The English [coauthor seminar](../seminar/README.md) presents the manuscript in 29 main slides with a 27-minute talk and 3-minute discussion, plus 9 optional backup slides. It follows five sections: introduction, related work/comparison, approach/verification, experimental results, and conclusion. Slides use concise bullets, tables, and comparison plots. The [presentation PDF](../../artifacts/public/paper1-seminar-001/coauthor-seminar-2026-10-08-001/coauthor-seminar-v01-en.pdf), [English presenter notes](../../artifacts/public/paper1-seminar-001/coauthor-seminar-2026-10-08-001/coauthor-seminar-v01-en-notes.pdf), and [LaTeX source](../seminar/coauthor-seminar-v01-en.tex) cover the method, existing results, and their limits. External studies are compared by central objectives, not evaluated as experimental baselines. The earlier Korean edition is retained in run coauthor-seminar-2026-10-07-001. Manuscript and experiment records remain unchanged.

- CoC means Chain of Causation; EBLC means Evidence-Bound Lifecycle Contracts; CNL means Controlled Natural Language.
- P0: CoC alone. P1: our existing natural-language constraints appended to CoC. P2: the same rule content developed through EBLC, checks, and CNL generation.
- The primary empirical comparison is P1/P2 versus P0. P1–P2 is an internal development-path comparison, not competition with an external method.
- The method explicitly follows **task → constraint fields → actual logical condition → generated CNL → evaluation verdict**.
- Scene measurements, supplied rules, and modeling assumptions have separate roles. CNL follows the original CoC in the requirement text; labels and solver verdicts are not model-input hints.
- Supported specification error injection is in scope as a quality evaluation. EBLC test-generation systems, runtime monitoring, real-road extraction validation, and vehicle deployment remain outside this paper.

## Preceding manuscript

The author identified [revision v01](../../../01-safety-constrained-coc/paper/manuscript/latex-kiee-review-2022-revision-v01/main.pdf), titled *Guard-Aware Trajectory Candidate Selection for Vision-Language Autonomous Driving: Safety-Constrained Chain-of-Causation*, as the preceding manuscript. It already proposes natural-language guards, lifecycle elements, paired contracts, and the task families. The present contribution develops a traceable source/field/logic/CNL interface. Reused generators and scoring principles are distinguished from newly executed experiments. Publication details are pending; no DOI, publication year, or venue is invented.

## Source organization

I Introduction; II Related Work; III Background; IV Proposed Method; V Experimental Setup; VI Results; VII Discussion; VIII Conclusion. The experimental Markdown contains both V and VI and is split at subsection B during integration. Bibliographic numbers and table numbers are global in the integrated PDF; local standalone-section labels remain in editable Markdown.

The earlier methods/settings package is a detailed historical evidence package, not the authority for the current prose or table layout. Current claims are governed by the maintained sections and their frozen source records.

## Remaining author checks

Confirm the author list, affiliations, biographies, funding, preceding manuscript citation, disclosures of related submission/publication, and the public code/data location and portable source bundle. AI drafting assistance is disclosed in the integrated draft. This is an author-review manuscript, not an assertion of submission readiness. Experiments and archived operational criteria have not been changed.

## Build and verification

The current English revision is reproduced by [build_layout.py](build_layout.py) with `--update-current`, for explicitly authorized in-place updates. It reads `main.tex`, checks approved hashes for the English related work, method, setup, and result prose, protects the frozen predecessor, Korean sources, and evidence records, and builds English with `pdflatex → bibtex → pdflatex → pdflatex`. Current output contains 9 figures and 16 tables (25 pages). Table 2 reports native execution checks; Table 10 includes position-hold dataset sizes. V.A.3 defines the position-hold additional-training protocol. VI.A and Figure 6 report all before/after position-hold strata with identical evaluation inputs for P0, P1, and P2; VI.B and Table 11 retain six-task performance. V.A.6 defines the archived representation, robustness, image-intervention, and error-layer evaluations. Tables 12–15 report them in VI.E–H; Table 16 retains unseen numeric/time conditions. All four detailed evaluation tables use one column. Figure 2 explains scene-specific grounding, Figure 6 shows position-hold learning, Figure 7 shows the reasoning-prompt controls, Figure 8 shows contract-pair accuracy and association shuffling, and Figure 9 illustrates the SMT boundary. The [manuscript figure renderer](../../experiments/paper1_external_methods/build_reasoning_manuscript_figure.py) reads the frozen comparison result without modifying it. Experiments, original figure assets, and bilingual evidence packages are preserved. [Verification report](REPORT_KO.md) records the current checks and remaining template warnings.

Build from the repository root with `make -C projects/04-guardsynth-coc/paper/ieee-access`. The recipe compiles this directory's `main.tex` with the stable job name `ieee-access-manuscript-en` and regenerates BibTeX references. The PDF and auxiliary files stay here. Publisher assets and figures are local; the unmodified IEEEtran class and bibliography style are in `template/`. Edit `references.bib` and maintained section sources rather than generated build files.

The frozen build recipe records bilingual generation; it intentionally refuses to overwrite a completed run containing `RESULT.json`. This historical snapshot remains evidence; the maintained English manuscript builds in this directory. [Verification report](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/REPORT_KO.md) records checks and remaining warnings.

## Primary position-hold learning result (2026-10-08)

The [frozen experiment report](../../artifacts/public/paper1-position-hold-training-001/position-hold-training-2026-10-08-001/REPORT_KO.md) supplies the primary learning comparison. Each of nine existing temporal adapters receives 960 rows of additional training; all arms receive the same P2 CNL at evaluation before and after training. Figure 6 shows both durations and both numerical representations; Supplement S12 retains exact tabular counts. The separate earlier XY regression remains reported as a limitation. Supplement S12 retains the full protocol and records. These are synthetic candidate-selection results, distinct from preliminary Alpamayo/converted-nuScenes trajectory-generation diagnostics.

The [position-hold manuscript renderer](../../experiments/paper1_external_methods/build_position_hold_manuscript_figure.py) plots the frozen `comparison_metrics.csv`. Reproduce it with `runtime/alpamayo/ar1_venv/bin/python projects/04-guardsynth-coc/experiments/paper1_external_methods/build_position_hold_manuscript_figure.py`, then run the English build recipe.

## From video observations to a scene-specific constraint

IV.B.3 (PDF pages 7–8), Preparing and Binding Supplied Scene Inputs, describes review of supplied observations and rules, confirmation of applicability, and mapping accepted inputs to EBLC fields. It links Figure 1 and Table 3 and explicitly distinguishes this workflow from evaluated automatic video extraction or exhaustive constraint discovery. The experimental settings, results, and numerical values remain unchanged.

Figure 2 (PDF page 8) expands IV.B.3 into separate supplied-observation and supplied-rule review paths, human confirmation, source-preserving EBLC input binding, and deferral. The illustration is reproduced by [build_video_grounding_manuscript_figure.py](../../experiments/paper1_external_methods/build_video_grounding_manuscript_figure.py) using `runtime/alpamayo/ar1_venv/bin/python`, followed by the English build recipe. It does not depict an evaluated automatic extractor.

## Supplied-input research scope (2026-10-08)

Automatic LLM or perception-based constraint extraction and its performance validation are outside this paper. The methods and first contribution describe selection and binding of supplied inputs. Implemented specification/correspondence checks and model action-selection evaluation remain in scope. Figure 2 retains its 30% display reduction. Experimental settings, results, and all numerical values remain unchanged.
