# Experiments and Results

This section defines the experimental basis for evaluating behavioral benefits and specification checkability. It introduces the comparison conditions, tasks, and data, then describes the model and training budgets, reference judgments, and evaluation metrics.

## A. Evaluation Objectives and Setup

Table E1 defines the training-input conditions: CoC alone (P0), CoC with the existing natural-language constraint (P1), and CoC with EBLC-derived CNL (P2). We evaluate the behavioral effects of adding constraints and the checkability of the EBLC-to-CNL path. P1 and P2 are our two constraint-enhancement approaches; their comparison concerns development paths.

**Table E1. Comparison conditions and roles**

| Condition | Information added to CoC during training | Evaluation role |
|---|---|---|
| P0 | No additional constraint | CoC-only baseline |
| P1 | Existing natural-language behavioral constraint | Our preceding constraint-enhancement approach |
| P2 | CNL generated after specifying and checking the same rule in EBLC | Formally supported constraint-development path |

In the six-task study, the three conditions use the same images, candidates, reference labels, and data splits. P1 and P2 receive constraints during both training and evaluation. P2 receives the generated CNL.

Two examples may have the same image, original CoC, and action candidates but different waiting requirements. For example, entry 0.5 seconds after the zone becomes clear is permitted under a 0.5-second rule but prohibited under a 1.5-second rule. The reference action can therefore differ between the two examples. In this six-task comparison, because P0 does not receive the waiting rule, it sees the same input in both cases and lacks the information needed to distinguish them.

The six-task comparison therefore measures how well models use constraints supplied during training and evaluation. A separate position-hold learning study supplies the same rule to every condition at evaluation and compares each checkpoint before and after additional training. Neither study tests performance when constraints are omitted during evaluation.

### Dataset Generation and Splits

We construct synthetic action-selection examples from schematic scenes, supplied rule values, and candidate summaries. The temporal generator varies clearance times, waits, candidate timings, and label assignments. Static examples apply maximum-speed, minimum-clearance, and minimum-entry-delay rules; maneuver examples apply stopping and lane-change rules. A reference program uses the supplied rules and the candidates' numerical values to determine allowed actions and the reference answer. Candidate scalars are supplied in text, rather than measured from images by the VLM.

Each example contains an image reference, original or constraint-augmented CoC, candidate descriptions, and a selection instruction. The reference label is retained as the training target or evaluation answer. P0, P1, and P2 share the same examples and splits, while their constraint text differs. Pairs keep the scene and candidates fixed but change the rule, which can change the reference answer.

Table E5 reports training, validation, and primary-test rows per input condition. Static training contains 192 rows per subtype, with 48 primary-test rows per subtype. Maneuver training contains 192 rows each for stopping and lane change, with 48 primary-test rows each. Repeating the experiment over three optimization seeds does not create new independent examples.

**Table E5. Synthetic dataset sizes per input condition**

| Family | Training rows | Validation rows | Primary-test rows |
|---|---|---|---|
| Temporal | 960 | 240 | 240 |
| Static | 576 | No separate split | 144 |
| Maneuver | 384 | No separate split | 96 |
| Position hold | 960 | 128 | 256 |

Temporal training, validation, and test images have no identical-pixel overlap. All 13 static primary-test images occur in training, and maneuver data reuse two diagrams across splits. Rows therefore represent constructed examples, not independent road videos. Supplement S1 and S8 report split inventories.

Secondary temporal evaluations use 240 rows each for paraphrasing and unseen durations. Static paraphrase and unseen-value sets each contain 144 rows; maneuver paraphrase, unseen-value, and combined hard-condition sets each contain 96 rows. Paraphrase sets reuse primary-test scenes, so these evaluations must not be pooled as independent scenes.

### Model and Training Settings

We use Qwen3-VL-2B-Instruct with LoRA and optimization seeds 42, 17, and 123. Within each task family, P0, P1, and P2 use the same examples, three epochs, optimizer settings, and final-checkpoint policy. Temporal, static, and maneuver fits perform 180, 108, and 72 optimizer updates, respectively. LoRA rank/alpha/dropout are 8/16/0.05; batch size is 2 with accumulation 8, AdamW learning rate is 0.0002, and weight decay is 0.01. All evaluations use the final checkpoint; validation scores do not select it. Supplement S1 and S8 provide detailed budgets.

### Position-Hold Learning with Identical Evaluation Inputs

The position-hold study tests whether including constraints during training improves compliance when evaluation information is held fixed. It continues the nine existing temporal adapters (P0, P1, and P2; seeds 42, 17, and 123) with 960 position-hold rows each, using three further epochs and 180 optimizer updates with the settings above. P0 training receives original CoC, P1 receives CoC with a natural-language rule, and P2 receives CoC with CNL generated from a restricted position-hold EBLC profile. Before and after this training, every adapter is evaluated with identical P2 CNL, images, and candidate descriptions. The adapters retain their different prior training histories; this comparison does not independently isolate verification or wording effects.

The rule requires remaining within 0.2 m of the initial position for either 0.5 or 2.0 s, including the end time. Synthetic candidate profiles are presented as XY waypoints or precomputed interval-maximum distances from those same waypoints. Images are generated diagrams of the profiles. Each profile produces eight related rows: two label rotations, two durations, and two representations. The profile-disjoint training, validation, and test sets contain 120, 16, and 32 profiles, respectively, giving the row counts in Table E5. The final checkpoint is fixed; validation does not select it. These are candidate-selection examples, separate from the preliminary Alpamayo trajectory-generation diagnostics on PhysicalAI and converted nuScenes inputs.

An independent integer calculation checks every supplied point up to the release time using x squared plus y squared at most 200 squared, with coordinates in millimeters. Leaving the permitted radius and returning before release still violates the rule. The reference answer is the highest-progress allowed candidate. All 5,376 candidate checks across the three splits agree with SMT. Main results use the strict 0.2 m radius; a 0.01 m tolerance is reported only as an auxiliary measure. Each duration--representation stratum contains 64 test rows, evaluated over three seeds, yielding 192 predictions rather than 192 independent road scenes. Earlier diagnostic profiles are disjoint and are reevaluated separately as a regression check. Supplement S12 gives the profile semantics, protocol, and complete records.

### Candidate References and Label Assignment

Each example supplies an image, original or constraint-augmented CoC, and candidate descriptions; Qwen3-VL-2B-Instruct is trained to output a candidate label A, B, C, or D. In the synthetic temporal task, independent integer arithmetic uses the clearance time and supplied wait to determine admissible candidates. The highest-utility admissible candidate is the reference action. Both permitted and prohibited candidates remain alternatives, while the supervised response contains only the reference label. EBLC candidate verdicts are compared with this independent admissibility calculation and retained as metadata, not copied into the prompt.

The temporal generator assigns utility values 110, 100, 85, and 0 to ordered candidate templates; no distance or speed calculation produces these scores. The target depends on their ordering among admissible candidates. During dataset construction, A–D are cyclically reassigned to those behaviors, so the same admissible action can have different output letters. This reduces a fixed-letter shortcut; it does not remove shortcuts from the supplied numeric candidate values or establish visual scene understanding.

The main metrics are **accuracy** against the highest-progress admissible candidate, **violation rate**, and **contract-pair accuracy**, which requires both members of a pair to be correct. An admissible but lower-progress choice is inaccurate without violating the contract. Six-task tables show three-seed means. The position-hold table reports accuracy and violation counts over three seeds, with 192 predictions per duration and representation. Compliant completion is auxiliary and is not independent evidence when it equals one minus violation rate.

### External Comparisons and Reasoning-Prompt Controls

Direct performance comparisons require compatible inputs, outputs, and evaluation units. The native translators in Table RW2 return logic expressions, while DriveLM and DriveVLM use driving tasks and metrics that differ from our numerical candidate selection. Together with the recorded resource limitations, these differences prevent a shared-task comparison using the inspected original execution paths. Adding our constraints or a new output adapter would change the method being evaluated.

We therefore conduct a supplementary comparison using Zero-shot CoT and basic Plan-and-Solve prompts on the existing final P0 checkpoints. Zero-shot CoT uses its step-by-step trigger followed by answer extraction. Plan-and-Solve uses the original basic planning-and-solving prompt, with direct extraction when the specified answer marker is present and a second generation otherwise. We use neither PS+ nor self-consistency. These are transfers of prompting procedures to our VLM task, not reproductions of the original language-model benchmarks. [Zero-shot CoT](https://arxiv.org/abs/2205.11916), [Plan-and-Solve](https://aclanthology.org/2023.acl-long.147/)

Both controls retain the P0 image, original CoC, and candidate descriptions. No rule thresholds, EBLC, CNL, solver verdicts, or reference labels are added to the model input, and no additional training is performed. Each method evaluates 240 temporal, 144 static, and 96 maneuver rows for each of seeds 42, 17, and 123, giving 2,880 scored predictions. With greedy decoding, one output is reused for identical image-and-prompt inputs within each method and checkpoint. There are 120, 24, and 38 unique inputs per family, yielding 1,092 first-stage generations across both methods and three seeds.

The native reasoning caps are 128 tokens for Zero-shot CoT and 256 for Plan-and-Solve, with up to 32 tokens for answer extraction. These are unequal inference budgets. Accuracy, violation rate, and pair accuracy use the existing reference rules; invalid answers remain in the accuracy denominator and are reported separately. We also inspect whether the first stage produces reasoning or only an option label.

### Representation, Robustness, and Error-Checking Evaluations

The following archived evaluations examine representation, wording, visual input, and specification errors. They use existing checkpoints and records; their rows are not added to the primary-test denominator. Tables E6, E7, E8, and E3 report these complementary evaluations.

**Constraint representations.** The temporal experiment includes three additional arms: `NATURAL_GUARD`, an alternative natural-language expression of the supplied rule; `LOGIC_GUARD`, logical text expressing that rule; and `SHUFFLED_GUARD`, natural-language guards whose correspondence with training cases is shuffled. Together with P0, P1, and P2, these yield six arms and three seeds. Each fit uses the same 960 training rows and 180 updates. Every arm receives 240 rows in each evaluation set. Correct case–guard associations are restored at evaluation for the shuffled arm. Logical text is a model input, not an internal solver. Supplement S1 and the additional temporal analyses retain the exact formulations and budgets.

**Wording and combined conditions.** Paraphrase evaluations change the constraint wording while retaining the case, candidate measurements, and intended rule. Temporal P1 and P2 receive the same held-out formulation; P0 and the temporal logical-text arm are unchanged in this test. The 240 temporal, 144 static, and 96 maneuver rows reuse their primary-test cases. A separate 96-row hard maneuver set combines negation, clause order, equality boundaries, and m/cm units. The latter tests their joint effect rather than isolating any one factor. All results use the existing final checkpoints and three seeds.

**Image interventions.** A follow-up temporal diagnostic pairs original images with blank images and images redrawn with clearance 1.0 s later. CoC, constraint text, candidates, and source reference labels remain fixed. Each image condition has 24 rows: three semantic parameter groups, two waiting rules, and four label rotations. Nine existing P0/P1/P2 adapters produce 648 predictions across these three conditions, as part of the 2,160-prediction follow-up diagnostic. We report source-reference accuracy, violation rate, and changes from the original-image selection. Because the redrawn image conflicts with the retained source, its scores describe an input intervention rather than ordinary scene accuracy. Supplement S9 retains all diagnostic strata; no new training is performed.

**Error injection and checking layers.** The balanced quality set contains 24 cases for each of six supported mutations, 24 shared-source/specification errors, and 24 valid contracts, totaling 192 cases. Supported mutations change CNL negation or thresholds, delete release conditions, reverse comparisons, change specification thresholds, or use incorrect units. Schema checks examine supported fields and units; source correspondence compares fields with supplied inputs; Core–environment checks compare encoded restrictions with the independent reference rule; and CNL correspondence checks the generated wording. Shared-source errors change the trusted input and specification together. Valid contracts measure false rejection and are excluded from the error-detection denominator. The existing S3/D4 records are counted once, not as new evidence from the follow-up evaluation.

## B. Position-Hold Learning Under Identical Evaluation Inputs

Our primary learning comparison asks whether models better follow a supplied rule after training with constraints, while keeping evaluation inputs identical. The position-hold learning figure reports accuracy and strict violation rates before and after position-hold training under the protocol in Section V.A, Position-Hold Learning with Identical Evaluation Inputs. The two representations describe the same candidate profiles; neither requires the model to generate a trajectory.

![Primary position-hold learning comparison: accuracy above and strict violation rate below, before versus after additional training](figures/position-hold-learning-en.png)

Gray bars show results before additional training and blue bars afterward. Each bar pools 64 test rows across three seeds (192 predictions); labels show percentages rounded to one decimal. All arms receive identical evaluation inputs. Exact counts and the separate earlier XY regression remain in Supplement S12 and the [frozen experiment report](../../artifacts/public/paper1-position-hold-training-001/position-hold-training-2026-10-08-001/REPORT_KO.md).

For the 2.0 s rule with interval maxima, the position-hold learning figure shows that P0, P1, and P2 end with 22/192, 1/192, and 0/192 violations, respectively (11.46%, 0.52%, and 0%). P2 improves from 81.77% to 98.44% accuracy and from 20 to zero observed violations; P1 reaches the same accuracy with one violation. Since every condition receives the same rule at evaluation, this result is not explained by withholding that rule from P0 at evaluation. With XY waypoints, P2 improves from 39.58% to 97.92% accuracy but retains 4/192 violations. The 0.5 s results also distinguish compliance from reference-answer accuracy: P0 makes no prohibited selections with interval maxima, yet reaches only 67.19% accuracy, compared with 94.79% for P2.

These improvements do not resolve the earlier XY diagnostic. After training, that separate 2.0 s regression set still yields 79/192 violations for P1 and 77/192 for P2. Its numerical distribution differs: the smallest prohibited overshoot is 1 mm, whereas the new primary test has a minimum prohibited overshoot of 22 mm. The two sets are not pooled. Supplement S12 retains both strict and tolerance-based regression results. The primary findings therefore support improved selection on the new synthetic test, with remaining sensitivity to representation and small boundary overshoots; they do not establish continuous-time safety, real-scene generalization, or a trained Alpamayo remedy.

## C. Performance Across Behavioral Tasks

This section first reports primary action-selection performance and the reasoning-prompt controls. It then examines contract changes, constraint representations, wording and combined conditions, visual-input interventions, and the layers that detect specification errors. Unseen numeric conditions and the scope of these evaluations are discussed separately.

We evaluate whether adding behavioral constraints to CoC improves candidate selection across six synthetic tasks. We compare P0, P1, and P2, defined in Table E1, using action-selection accuracy and constraint violation rate. Table E2 reports the primary results.

This subsection evaluates the model’s action choices across the six tasks listed in Table M1. A reference program applies the supplied rules to identify allowed candidates and selects the one with the highest progress score as the reference answer. We measure accuracy by comparing the model’s choice with this answer. Separately, we count a constraint violation when the model selects a prohibited candidate.

As an auxiliary check, we compare the reference program’s admissibility judgments with the corresponding SMT verdicts, using the same rules and candidate values. This comparison checks whether the two implementations agree. The checks of whether the EBLC specification correctly expresses the intended restrictions and release conditions are described in Section IV.D.

**Table E2. Primary accuracy / violation rate, %, mean over three seeds**

| Task | P0 | P1 | P2 |
|---|---|---|---|
| Maximum speed | 50.00 / 24.31 | 100.00 / 0.00 | 100.00 / 0.00 |
| Minimum clearance | 50.00 / 24.31 | 100.00 / 0.00 | 100.00 / 0.00 |
| Minimum entry delay | 50.00 / 24.31 | 100.00 / 0.00 | 100.00 / 0.00 |
| Entry after clearance and waiting | 49.86 / 19.17 | 96.81 / 1.39 | 98.06 / 0.83 |
| Stopping | 50.00 / 23.61 | 100.00 / 0.00 | 100.00 / 0.00 |
| Lane change | 50.00 / 38.19 | 100.00 / 0.00 | 97.92 / 0.00 |

Table E2 reports mean accuracy and violation rates over three seeds. P1 and P2 have higher accuracy and lower violation rates than P0 for all six task types. Temporal accuracy gains over P0 are 46.94 and 48.19 percentage points for P1 and P2, with violation reductions of 17.78 and 18.33 points. P1 and P2 tie in the three static types and stopping.

The per-candidate records in Supplement S8 show that residual P2 lane-change errors select admissible but lower-progress candidates; compliant completion is 100%. Temporal P2 compliant completion is 99.17%, as reported in Supplement S2.

The mean results in Table E2 summarize the comparison with P0. Supplement S2 and S8 report seed-level variability and additional evaluation conditions. P2 does not outperform P1 under every seed and evaluation condition. We report both paths relative to P0 and have not conducted a formal noninferiority test between P1 and P2.

## D. Supplementary Comparison with Reasoning Prompts

This comparison tests whether adding generic reasoning instructions to CoC-only checkpoints changes candidate selection without supplying the missing behavioral rule. Figure E6 compares the two controls defined in Section V.A, External Comparisons and Reasoning-Prompt Controls with the archived P0, P1, and P2 predictions on the same primary-test rows. Bars show three-seed means and points show individual seeds.

Across the 480 rows, mean accuracy is 49.93% for P0 and for each reasoning-prompt control. Violation rates are 23.06% for P0, 22.64% for Zero-shot CoT, and 22.71% for Plan-and-Solve. These pooled percentages weight task families by their row counts. Both controls have 0% contract-pair accuracy in every family, and all final answers are valid candidate labels. The violation changes depend on the task: temporal and lane-change rates decrease slightly, while static rates increase. Figure E6 retains these differences.

![Figure E6. Reasoning-prompt comparison](../../artifacts/public/paper1-reasoning-comparison-001/reasoning-comparison-2026-10-07-001/reasoning_comparison.png)

Figure E6. Supplementary reasoning-prompt comparison on existing P0 checkpoints. ZS-CoT denotes Zero-shot CoT and PS denotes basic Plan-and-Solve. Bars show accuracy and constraint violation rates; dots show the three optimization seeds. P1 and P2 are archived results with additional rule information. The dotted 50% line marks the fixed-output accuracy ceiling for conditions without supplied constraints. This is a prompting-strategy transfer, not a reproduction of the original methods’ benchmark scores.

The first-stage outputs limit the interpretation. All 546 unique Zero-shot CoT cases return short option-label strings; Plan-and-Solve does so in 498 of 546 cases. Its remaining 48 cases, all static, generate longer text but reach the 256-token reasoning cap before answer extraction. Thus, issuing a reasoning prompt does not establish that these label-trained checkpoints perform a complete multistep reasoning procedure.

Every distinct P0 image-and-prompt group has conflicting reference labels under different rules. The best fixed output per group can therefore achieve at most 50% accuracy in each family. Additional reasoning cannot identify an omitted experimental rule from identical inputs. Figure E6 consequently describes the response of the current checkpoints to reasoning instructions; differences from P1 or P2 also reflect rule availability and do not establish equal-information algorithm superiority.

## E. Contract Changes and Correct Association

Changing the rule while keeping the scene and candidates fixed tests whether models adjust their action choices accordingly. We also test whether correct pairing between cases and constraints during training matters by comparing correctly paired data with shuffled pairings.

The left panel of Figure 6 reports contract-pair accuracy, which is 0% for P0 in all three task families. In temporal, static, and maneuver families, respectively, P1 achieves 93.61%, 100%, and 100%, and P2 achieves 96.11%, 100%, and 97.92%. Constraint-conditioned models can change their selections when the rule changes while the visual input remains fixed. P0's low values must be interpreted with its missing contract information.

The right panel of Figure 6 compares correctly paired and shuffled training data. Shuffling training-time case–constraint associations while restoring correct constraints at evaluation gives accuracies of 50.56%, 50.69%, and 49.65%. Temporal shuffling uses natural-language guards, whereas new static and maneuver shuffling permutes P2 CNL within subtype; these are not pooled as one identical intervention. The results support the importance of correct case–constraint association beyond adding sentences alone.

![Figure 6. Contract pairs and association shuffling](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/figures/contract-linkage-en.png)

Figure 6. Left: contract-pair accuracy. Right: action accuracy of P2 with correct associations versus shuffled training associations. Points are three-seed means; static and maneuver values aggregate their subtypes.

In one recorded prediction with clearance at 11.0 s and a 1.5 s wait, P0 chooses entry at 11.5 s, while P1 and P2 choose the admissible boundary at 12.5 s. Another P2 example enters 0.1 s too early. These post-hoc explanatory cases are detailed in Supplement S5.

## F. Constraint Representation and Generalization

Comparing different expressions of the same rule tests whether high performance depends on EBLC-derived CNL alone. Table E6 reports the six temporal arms defined in Section V.A, Representation, Robustness, and Error-Checking Evaluations. The primary and unseen-duration columns each contain 240 rows per arm and seed; the unseen waits are 0.8 and 1.8 s, compared with 0.5 and 1.5 s during training.

**Table E6. Temporal constraint representations: accuracy / violation rate, %, three-seed means**

| Arm | Primary | Unseen wait |
| --- | --- | --- |
| P0 | 49.86 / 19.17 | 49.86 / 18.47 |
| P1 | 96.81 / 1.39 | 96.67 / 2.22 |
| P2 | 98.06 / 0.83 | 96.67 / 1.53 |
| NATURAL_GUARD | 98.06 / 1.11 | 98.61 / 0.56 |
| SHUFFLED_GUARD | 50.56 / 19.72 | 50.97 / 18.89 |
| LOGIC_GUARD | 99.17 / 0.14 | 81.25 / 0.83 |

In Table E6, alternative natural-language guards match P2 primary accuracy at 98.06%, while logical text reaches 99.17%. On unseen durations, the natural-language arm reaches 98.61%, but the logical-text arm falls to 81.25% despite a violation rate of only 0.83%. Low violation does not imply selection of the highest-progress admissible action.

The shuffled arm remains near 50% accuracy even though correctly associated guards are supplied at evaluation. This agrees with the binding comparison in Figure 6. Together, the results support supplying the rule and preserving its correspondence with the case; they do not establish universal behavioral superiority of CNL over other representations. The formal path additionally provides the checks reported in Table E3.

## G. Sensitivity to Wording and Combined Conditions

Table E7 compares primary results with changed wording and the combined hard maneuver conditions. Each paraphrase row retains its corresponding primary cases and rules, so changes describe sensitivity to wording rather than performance on additional independent scenes. The hard row is a separate combined-condition test.

**Table E7. Wording and combined conditions: accuracy / violation rate, %, three-seed means**

| Evaluation | P0 | P1 | P2 |
| --- | --- | --- | --- |
| Temporal: Primary | 49.86 / 19.17 | 96.81 / 1.39 | 98.06 / 0.83 |
| Temporal: Paraphrase | 49.86 / 19.17 | 90.56 / 5.00 | 96.94 / 1.25 |
| Static: Primary | 50.00 / 24.31 | 100.00 / 0.00 | 100.00 / 0.00 |
| Static: Paraphrase | 50.00 / 24.31 | 93.29 / 0.00 | 80.32 / 7.87 |
| Maneuver: Primary | 50.00 / 30.90 | 100.00 / 0.00 | 98.96 / 0.00 |
| Maneuver: Paraphrase | 50.00 / 30.90 | 100.00 / 0.00 | 97.92 / 2.08 |
| Maneuver: Combined hard | 50.00 / 30.21 | 94.10 / 0.69 | 91.32 / 1.04 |

For temporal paraphrases in Table E7, P2 retains 96.94% accuracy with 1.25% violations, compared with 90.56% and 5.00% for P1. Static paraphrases show the reverse ordering: P2 falls from 100% to 80.32% accuracy with 7.87% violations, while P1 reaches 93.29% with no observed violations. Both the favorable temporal result and the unfavorable static result are needed to characterize the CNL input interface.

On combined hard maneuver cases in Table E7, P1 reaches 94.10% accuracy and 0.69% violations, whereas P2 reaches 91.32% and 1.04%. P2 contract-pair accuracy also falls from 97.92% on the primary maneuver test to 82.64% on the hard set. The combined test does not identify whether negation, order, boundary equality, or units individually cause the errors.

A separate follow-up wording diagnostic in Supplement S9 contains 24 rows per formulation and seed. Its second paraphrase lowers P1 accuracy from 100% to 76.39% and P2 from 95.83% to 77.78%; violations rise to 15.28% and 9.72%, respectively. These small exploratory strata are separate from Table E7. They reinforce that a checked rule representation does not guarantee stable interpretation by the learned model under every wording change.

## H. Dependence on Visual Input

The paired image interventions examine whether candidate selections change when the visual input is removed or conflicts with the retained textual case. Table E8 reports source-reference accuracy and violation rate for the 24-row temporal diagnostic in Section V.A, Representation, Robustness, and Error-Checking Evaluations. These results are separate from primary-test performance.

**Table E8. Image interventions: source-reference accuracy / violation rate, %, three-seed means**

| Image | P0 | P1 | P2 |
| --- | --- | --- | --- |
| Original | 50.00 / 22.22 | 100.00 / 0.00 | 98.61 / 1.39 |
| Blank | 50.00 / 13.89 | 81.94 / 2.78 | 76.39 / 1.39 |
| Redrawn (+1 s) | 50.00 / 19.44 | 87.50 / 0.00 | 79.17 / 1.39 |

In Table E8, P2 source-reference accuracy falls from 98.61% with the original image to 76.39% with a blank image and 79.17% with the redrawn image. Its selection changes on 25.00% and 19.44% of the corresponding paired cases. P1 changes on 18.06% and 12.50%, with accuracy falling from 100% to 81.94% and 87.50%. Thus, the selected labels are sensitive to visual input, even though numerical candidate values are also supplied in text.

P2 violation rate remains 1.39% in all three image conditions in Table E8. The accuracy loss therefore need not be an increase in prohibited selections; admissible but lower-progress choices can also change. Retaining substantial accuracy with a blank image does not establish visual grounding, and sensitivity to a conflicting image does not prove that the model interprets the depicted event correctly. Three semantic parameter groups and three seeds make this an exploratory input-dependence check, not evidence of real-road perception accuracy.

## I. Checkability of Specifications and CNL

To assess specification quality, we test whether the checking pipeline detects errors in EBLC specifications and generated CNL while accepting valid contracts. We also test whether the encoded temporal restriction rejects premature entry and permits entry at and after release.

We inject errors involving negation, thresholds, release conditions, comparison direction, and units into the schema, evidence, Core, and CNL checking path. Supplement S3 reports the six supported types and their checking layers. This quality evaluation is distinct from model accuracy.

Prediction accuracy and violation rate are calculated over model test predictions. The checks in Table E3 count tested specifications, while boundary-query checks count logical queries. These counting units are reported separately.

**Table E3. Specification and CNL checks by category and layer**

| Input category | Detected / cases | Checking layer |
| --- | --- | --- |
| CNL negation change | 24/24 | CNL correspondence |
| CNL threshold change | 24/24 | CNL correspondence |
| Release deletion | 24/24 | Core–environment |
| Comparison reversal | 24/24 | Core–environment |
| Specification threshold change | 24/24 | Source and Core |
| Unit error | 24/24 | Schema |
| Shared source/specification error | 0/24 | No layer detects |
| Valid contract | Not applicable | All 24 accepted |

Table E3 shows that all 144 mutations in the six supported categories are detected and all 24 valid contracts are accepted, with no false rejection. All 24 shared-source/specification errors are missed, giving 144 detections among 168 erroneous cases, or 85.71%. The layers matter: a CNL negation change is found by comparing the sentence with its specification, while an incorrect unit is rejected by the schema. The aggregate is not a SAT-only detection rate.

The shared-source row of Table E3 identifies a failure that internal consistency cannot settle. If the supplied waiting duration and its EBLC field are both changed to the same incorrect value, source correspondence and the reference comparison can still agree. All 24 shared-source errors remain internally SAT. Independent review of the rule evidence is needed to find this failure; another solve of the same internally consistent inputs does not provide it.

Bypassing the checks accepts all 192 cases. Applying them accepts 48: the 24 valid contracts and the 24 shared-source errors. This comparison demonstrates rejection of supported mutations while retaining the undetected negative controls. It does not measure naturally occurring error prevalence, and the same S3/D4 injection records are not counted again as a second experiment.

All 100 temporal boundary queries match expected outcomes: 76 SAT, 24 UNSAT, and no UNKNOWN. Figure 7 illustrates three queries around the release boundary for a 0.5-second wait. Additional candidate checks and comparisons with model judgments appear in Supplement S8.

![Figure 7. SAT and UNSAT around an admissibility boundary](../../artifacts/public/paper1-method-preservation-001/manuscript-revision-2026-09-30-001/figures/smt-boundary-en.png)

Figure 7. With clearance at 11.000 s and a 0.500 s wait, entry at 11.499 s is UNSAT; 11.500 s and 11.501 s are SAT. The 1 ms logical-time expansion does not imply vehicle-control precision.

In Figure 7, UNSAT excludes a prohibited entry rather than counting a defective specification. By contrast, increasing an injected wait by 100 ms makes an originally permitted query UNSAT, while removing the release restriction makes a prohibited query SAT. Unexpected outcomes require reviewing the source, threshold, and clause, then rechecking both sides of the boundary. An inconsistent base contract or UNKNOWN is not accepted as verification evidence. Supplement S3 retains the representative conflict set and response rules.

## J. Unseen Conditions and Interpretation

Tests with numerical values or waiting durations absent from training measure action-selection accuracy and constraint violation rate under new conditions. We also summarize additional tests of changed wording and input conditions to clarify the scope of the results.

**Table E4. Unseen numeric/time conditions: accuracy / violation rate, %, three-seed means**

| Task family | P0 | P1 | P2 |
|---|---|---|---|
| Temporal | 49.86 / 18.47 | 96.67 / 2.22 | 96.67 / 1.53 |
| Static | 50.00 / 22.92 | 99.54 / 0.00 | 97.22 / 0.23 |
| Maneuver | 50.00 / 30.90 | 100.00 / 0.00 | 98.96 / 0.00 |

As shown in Table E4, both constraint-enhancement paths outperform P0 on unseen numeric/time conditions.

Tables E6 and E7 show that generalization depends on both the input representation and the task. Table E8 reports exploratory image dependence, and Table E3 distinguishes supported checks from undetected shared-source errors. Specification-derived auxiliary-cost learning remains a separate secondary analysis in Supplement S6; it is not pooled with these evaluations.

The results concern supplied synthetic constraints and finite candidates. Textual scalars, repeated diagrams, one model, and three seeds limit claims about real-road visual understanding, closed-loop safety, or Alpamayo training. Constraint availability and the causal effect of verification are distinguished. Detailed variability, conditional intervals, and archived operational-criterion outcomes remain in the supplement.

Overall, multiple action tasks show benefits from constraint-enhanced CoC, while the EBLC-supported development path combines high action-selection performance with explicit checks of constraint errors and admissible/prohibited boundaries.
