# II. Related Work

This section reviews research connecting driving observations, reasoning, and actions, followed by traffic-rule specification and regulation-aware decision making. It then examines natural-language formalization and controlled natural language to clarify how GuardSynth relates to existing approaches.

## A. Reasoning-Based Autonomous Driving and CoC

Connecting visual observations to language-based reasoning and actions is an important direction in autonomous driving. Alpamayo-R1 combines Chain of Causation (CoC) reasoning with trajectory prediction and uses supervised fine-tuning and reinforcement learning to improve reasoning–action alignment. DriveLM represents relationships among perception, prediction, and planning questions and answers as a graph, while DriveVLM connects scene description, scene analysis, and hierarchical planning. These studies provide learnable representations of the process from observation to decision. [1](https://arxiv.org/abs/2511.00088), [2](https://arxiv.org/abs/2312.14150), [3](https://arxiv.org/abs/2402.12289)

Alignment between explanations and actions is also important for useful reasoning. Drive-R1 addresses reasoning–planning misalignment and history-based shortcut learning, using trajectory and meta-action rewards after supervised fine-tuning. Complementing this direction, we focus on how behavioral constraints are represented in learning data. We distinguish CoC explanations of why an action is taken from constraints restricting which actions are admissible in the situation, and combine the two. This distinction defines explicit normative information to accompany explanations, rather than presuming a general performance deficiency of existing reasoning models. [4](https://ojs.aaai.org/index.php/AAAI/article/view/37602)

DriveLM's graph connects perception, prediction, and planning questions, while DriveVLM uses scene description and analysis to support hierarchical planning. GuardSynth addresses a different interface: developing explicit behavioral conditions that accompany an existing action rationale. The conditions link supplied observations, rules, and assumptions to an EBLC profile, logical checks, and generated CNL. Our candidate-selection experiment therefore measures the use of supplied restrictions, rather than reproducing these systems' native driving tasks. [DriveLM](https://arxiv.org/abs/2312.14150), [DriveVLM](https://arxiv.org/abs/2402.12289)

General reasoning prompts provide another comparison direction. Zero-shot CoT elicits step-by-step reasoning before answer extraction, and basic Plan-and-Solve first requests a plan and then its execution. These instructions organize reasoning without supplying a case-specific rule. We use them as supplementary inference controls to examine whether additional reasoning instructions change action choices when the added constraint is absent. [Zero-shot CoT](https://arxiv.org/abs/2205.11916), [Plan-and-Solve](https://aclanthology.org/2023.acl-long.147/)

## B. Traffic-Rule Specification and Regulation-Aware Decisions

Machine-interpretable traffic rules provide a direct foundation for formalizing behavioral constraints. Esterle et al. express traffic rules in linear temporal logic (LTL) and apply them to compliance assessment on driving data. This approach gives applicability conditions and temporal relationships explicit semantics. Following this principle, we structure the subject and target, activation, persistence, release, and evidence links of CoC-augmenting constraints as EBLC elements. [5](https://arxiv.org/abs/2007.00330)

Retrieval-augmented reasoning offers another way to connect regulations with scenes. DriveReg retrieves situation-relevant traffic regulations and connects them to language-model reasoning to support compliance and interpretable decisions. Its central focus is retrieving and using applicable regulations. GuardSynth instead focuses on expressing selected behavioral constraints in an explicit intermediate representation, checking them within a restricted logical model, and conveying them as natural-language learning inputs. Regulation retrieval and constraint specification have complementary roles in obtaining supporting evidence and representing constraints. [6](https://ojs.aaai.org/index.php/AAAI/article/view/41168)

## C. Natural Language, Formal Specifications, and CNL

Translating natural-language requirements into formal specifications connects human-readable descriptions with machine-verifiable representations. NL2TL uses abstracted atomic propositions and language models to translate natural language into temporal logic, separating domain-specific proposition recognition from translation structure. nl2spec associates language fragments with subformulas and lets users revise these associations to resolve ambiguity. The former emphasizes learning and adapting a translation model, while the latter emphasizes interactive specification and user correction. [7](https://aclanthology.org/2023.emnlp-main.985/), [8](https://arxiv.org/abs/2303.04864)

Both methods formalize supplied language requirements. Their native outputs are temporal-logic expressions, not labels for our action candidates. GuardSynth additionally defines how CoC context, scene evidence, supplied rules, and assumptions populate a restricted contract and how the checked restriction returns to CoC through CNL. Translation quality and downstream candidate-selection accuracy consequently answer different questions. Applying a new candidate selector to nl2spec or NL2TL would evaluate an adapted pipeline, and we do not treat their native demonstrations as action-selection baselines. [NL2TL](https://aclanthology.org/2023.emnlp-main.985/), [nl2spec](https://arxiv.org/abs/2303.04864)

Controlled Natural Language (CNL) is also relevant when specifications are presented in readable language. Attempto Controlled English (ACE) restricts grammar and interpretation rules to connect natural-language sentences with formal representations. GuardSynth's CNL is not an implementation of ACE; it maps fields and clauses of a selected EBLC profile to restricted sentence patterns. Our focus is traceable correspondence between defined constraint elements and generated sentences, rather than semantic equivalence across unrestricted natural language. Logical verification, sentence correspondence, and the validity of scene evidence are consequently distinct review targets. [9](https://attempto.ifi.uzh.ch/site/pubs/papers/FLAIRS0601FuchsN.pdf)

## D. Positioning of This Work

Our preceding Safety-Constrained CoC manuscript already introduces natural-language execution guards and contract-pair evaluation over static, temporal, and maneuver tasks. GuardSynth retains that learning interface but develops a traceable source-to-specification-to-CNL path for producing its constraint component. The present P1 condition instantiates our earlier approach; P2 is its formally supported development path. Reused task generators and scoring principles are distinguished from newly executed experiments. [Preceding manuscript](../../../01-safety-constrained-coc/paper/manuscript/latex-kiee-review-2022-revision-v01/main.pdf)

These research directions establish foundations for learning driving reasoning, formalizing traffic rules, and connecting language with logic. Building on them, GuardSynth defines the scope, properties, and elements of CoC behavioral constraints and connects EBLC specification, restricted logical verification, CNL generation, and CoC augmentation. The focus is on organizing learning constraints through a consistent representation and verification procedure, rather than developing a new driving model or a general-purpose translator. Table 1 compares the central objectives of the selected studies; it is neither an exhaustive feature audit nor a performance ranking.

Table 1. Central objectives of related work and their relationship to GuardSynth.

| Study | Central objective | Representation or approach | Connection to this work |
|---|---|---|---|
| Alpamayo-R1; Drive-R1 [1, 4] | Reasoning–action alignment | CoC/CoT, supervised learning and RL | Useful supervision for action selection |
| DriveLM; DriveVLM [2, 3] | Reasoning from scenes to plans | Graph question answering; hierarchical planning | Structuring scene and action explanations |
| Esterle et al. [5] | Machine-interpretable traffic rules | LTL specifications | Explicit conditional and temporal semantics |
| DriveReg [6] | Regulation-aware decisions | Regulation retrieval and LLM reasoning | Connecting applicable rules and evidence |
| NL2TL; nl2spec [7, 8] | Formalizing language requirements | Temporal-logic translation; interactive revision | Language–specification correspondence |
| ACE [9] | Unambiguously interpreted language | Restricted grammar and formal interpretation | Principles of controlled expression |
| GuardSynth | Structuring constraints for CoC learning | EBLC → logical checks → CNL → CoC augmentation | Linking constraint model, verification, and learning inputs |

We assess learning utility by comparing CoC alone (P0) with constraint-augmented CoC (P1 and P2), using the same model and matched training budgets. P1 is our existing natural-language constraint approach, and P2 uses CNL generated from EBLC. Thus, P1/P2 versus P0 is the primary comparison, while P1 versus P2 compares representations within our proposed family. This experiment evaluates the effect of supplying constraints; it does not isolate a causal effect of logical verification. The paper covers constraint specification, verification, CNL generation, and learning use. EBLC-based test generation and runtime monitoring are subsequent applications.

## E. Native Execution Checks and Comparison Scope

Table RW2 records our checks of the selected methods' original execution paths. We ran their supplied examples without adding GuardSynth constraints or a candidate-selection adapter. These checks establish which native paths were exercised; they do not provide a shared-task performance ranking or a translation-accuracy benchmark.

**Table RW2. Native execution checks of selected external methods**

| Method | Native task or output | Execution checked in this study |
|---|---|---|
| nl2spec | Temporal-logic translation with language–subformula links | One original CLI example executed with three translation samples; interactive user correction was not exercised. |
| NL2TL | Temporal-logic translation of supplied requirements | Eleven original notebook examples executed using the official model weights. |
| DriveLM | Graph VQA and driving reasoning | Native inference not executed: the original LLaMA-7B base weights required by the inspected released challenge baseline were unavailable in our environment. |
| DriveVLM | Scene analysis and hierarchical planning | Native inference not executed: the inspected official repository contained project-page material, but no inference code or model weights. |

The DriveLM check concerns the released challenge baseline and is not a reproduction of the full DriveLM-Agent. Resource statements in Table RW2 describe the local environment and official sources inspected on October 7, 2026; they do not assert that resources are unavailable elsewhere. The completed translator demonstrations produced no predictions on our common candidate-selection task.

## References

- [1] NVIDIA, “Alpamayo-R1: Bridging Reasoning and Action Prediction for Generalizable Autonomous Driving in the Long Tail,” arXiv:2511.00088, 2025, revised 2026. [Paper](https://arxiv.org/abs/2511.00088).
- [2] C. Sima et al., “DriveLM: Driving with Graph Visual Question Answering,” ECCV, 2024. [Paper](https://arxiv.org/abs/2312.14150).
- [3] X. Tian et al., “DriveVLM: The Convergence of Autonomous Driving and Large Vision-Language Models,” 2024. [Paper](https://arxiv.org/abs/2402.12289).
- [4] Y. Li et al., “Drive-R1: Bridging Reasoning and Planning in VLMs for Autonomous Driving with Reinforcement Learning,” AAAI, vol. 40, no. 8, pp. 6708–6716, 2026. [Paper](https://ojs.aaai.org/index.php/AAAI/article/view/37602).
- [5] K. Esterle, L. Gressenbuch, and A. Knoll, “Formalizing Traffic Rules for Machine Interpretability,” IEEE CAVS, 2020. [Paper](https://arxiv.org/abs/2007.00330).
- [6] T. Cai et al., “Driving with Regulation: Trustworthy and Interpretable Decision-Making for Autonomous Driving with Retrieval-Augmented Reasoning,” AAAI, vol. 40, no. 45, pp. 38287–38295, 2026. [Paper](https://ojs.aaai.org/index.php/AAAI/article/view/41168).
- [7] Y. Chen, R. Gandhi, Y. Zhang, and C. Fan, “NL2TL: Transforming Natural Languages to Temporal Logics using Large Language Models,” EMNLP, pp. 15880–15903, 2023. [Paper](https://aclanthology.org/2023.emnlp-main.985/).
- [8] M. Cosler, C. Hahn, D. Mendoza, F. Schmitt, and C. Trippel, “nl2spec: Interactively Translating Unstructured Natural Language to Temporal Logics with Large Language Models,” CAV, 2023. [Paper](https://arxiv.org/abs/2303.04864).
- [9] N. E. Fuchs, K. Kaljurand, and G. Schneider, “Attempto Controlled English Meets the Challenges of Knowledge Representation, Reasoning, Interoperability and User Interfaces,” 2006. [Paper](https://attempto.ifi.uzh.ch/site/pubs/papers/FLAIRS0601FuchsN.pdf).

- [10] T. Kojima et al., “Large Language Models are Zero-Shot Reasoners,” NeurIPS, 2022. [Paper](https://arxiv.org/abs/2205.11916).
- [11] L. Wang et al., “Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models,” ACL, pp. 2609–2634, 2023. [Paper](https://aclanthology.org/2023.acl-long.147/).
