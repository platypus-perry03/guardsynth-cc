# IV. Proposed Method

This section follows the constraint-development process: selecting supplied action-relevant constraints and binding their evidence, specifying their meaning in EBLC, checking the executable representation, and generating CNL to augment CoC. The temporal example connects these stages; a separate qualitative profile defines how uncertain evidence affects constraint lifecycles. Model training and evaluation are described in the experimental section.

## A. Overview and Scope

GuardSynth preserves the action explanation in CoC while making conditions that restrict action selection explicit in a separate specification, then returning those conditions to a natural-language representation. Inputs comprise original CoC, scene observations available for the decision, and applicable rules with their evidence. Outputs comprise structured behavioral constraints, logical verification results under a restricted model, controlled natural language (CNL) generated from the specification, and an augmented learning input. The formal representation specifies condition semantics and verification scope; the language representation conveys those conditions to learning.

The process has four stages: select and bind supplied constraint candidates, specify accepted content in EBLC, check the supported logical representation, and render the checked restriction as CNL for insertion into the original CoC. Unexpected results return the specification for review; unconfirmed scene information remains unresolved.

![Figure 1. Processing workflow](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-005/figures/method-flow-en.png)

Figure 1. The upper row distinguishes four input roles; stages 01–04 below run from evidence binding to CoC augmentation. Solid arrows show processing order; the dashed path returns unexpected verdicts or UNKNOWN for revision. Unresolved candidates are held at stage 01. Real scenes require human confirmation of applicability evidence; synthetic experiments bind supplied conditions.

The inputs in Figure 1 provide non-interchangeable information. Original CoC supplies action and rationale context for identifying relevant constraint candidates. The other three inputs are defined below as observational values, behavioral rules, and interpretation scope.

**Observations: definition and example.** An observation describes the state of an entity, zone, or event at a specified time. Real-scene observations are linked to evidence such as video and its confirmation, whereas the primary synthetic experiment uses states supplied by the generating environment. “The conflict zone became clear at 11.0 seconds” is an event-time observation. Stage 01 in Figure 1 binds the entity and event to the observation; stage 03 uses the observed clearance time (clear_ms = 11000) as an input to the verification query. This observation alone does not determine a required waiting duration.

**Rules: definition and example.** A rule specifies which action is restricted under an applicability condition and when that restriction is released. “Do not enter for at least 0.5 seconds after clearance” is a supplied experimental rule. Stage 01 in Figure 1 confirms its applicability evidence; stage 02 specifies the restricted action and release_clear_ms = 500. The duration is neither an observed scene property nor a value inferred from CoC.

**Modeling assumptions: definition and example.** A modeling assumption states the scope within which inputs are interpreted and verified. “The zone is not reoccupied after clearance” allows continuous clearance to be represented by one clearance time. Stage 02 in Figure 1 records this assumption as contract scope; stage 03 uses it in the logical interpretation. If reoccupation is possible, the assumption must be reconsidered before applying the same single-time expression.

Consequently, the same observation at 11.0 seconds yields admissibility from 11.5 or 12.5 seconds under supplied waits of 0.5 or 1.5 seconds. Stage 04 in Figure 1 conveys the specified and verified restriction through CNL. Separating these roles prevents treating an observation as a rule or an assumption as an observed fact.

Executable numerical and qualitative profiles instantiate this approach. The learning experiments use a temporal profile and static/maneuver candidate-summary profiles constructed from supplied synthetic rules. A separate qualitative profile connects entities, zones, and events through observations and human review of real scenes. Both link specifications to evidence, but their inputs and semantics differ. We use the temporal contract as the running example and the qualitative profile to describe evidence uncertainty and constraint lifecycles.

## B. Selecting Supplied Constraints and Binding Evidence

### 1. Distinguishing Constraints from Other CoC Content

A behavioral constraint restricts available actions in a situation. For example, “a pedestrian is crossing” describes an observation; “yield to protect the pedestrian” provides an action rationale; “do not enter the conflict zone while the pedestrian occupies it” specifies a behavioral constraint; and “select the admissible action with the greatest progress” states an objective that ranks permitted actions. Satisfying an entry-permission condition does not force entry; selecting among permitted actions requires a separate objective.

Not every CoC sentence becomes a constraint. We select content with a relevant condition and an action restriction, while keeping observations, rationales, and selection objectives in their distinct roles. This prevents inventing thresholds or release conditions absent from CoC and its evidence. In particular, a waiting duration requires a supplied rule or separately established normative evidence.

### 2. Input Sources and Evidence Binding

To construct an EBLC specification, supplied CoC context, observations, and rules are reviewed for relevance to the action. The selected content binds entities, zones, and the decision time to the applicable restriction. Accepted inputs are mapped to supported fields with explicit assumptions, evidence references, and version information. The output of selection and binding is a constraint candidate with its supporting inputs, not a verified contract or a learning target.

Table M4 summarizes the source-to-field mapping. CoC supplies action and rationale context, observations supply scene bindings, rules supply restrictions and bounds, and modeling decisions specify interpretation scope. A statement appearing in CoC does not itself confirm that it applies to the current scene.

**Table M4. Source content and its mapping to specification inputs**

| Source | Selected content | Destination |
|---|---|---|
| Original CoC | Intended action, rationale, potential obligation | Constraint kind and relevance candidate; preserve the original CoC separately |
| Scene evidence or synthetic state | Target, zone, decision time, clearance event, candidate measurements | Entity bindings and query assignments; not rule thresholds |
| Supplied rule or reviewed rule evidence | Restricted action, applicability, comparison, bound, release requirement | EBLC obligation or `limits` fields with source references |
| Explicit modeling decision | Time scope, no reoccupation, completion convention | Versioned profile assumptions, disclosed with evaluation scope |

Following the mapping in Table M4, numerical bounds are read from supplied rule fields (`threshold`, `max_decel`, `max_jerk`, `min_gap`, or the temporal wait). They are not inferred from image pixels. Candidate measurements are separate inputs used when a candidate is queried; the encoding of these bounds is defined in the specification subsection.

### 3. Preparing and Binding Supplied Scene Inputs

Preparation of real-scene inputs combines supplied or human-reviewed observations with an applicable supplied rule. The input roles in Figure 1 and Table M4 become the following grounding steps; a rule is not inferred merely because an action appears in a video. The grounding diagram below illustrates their combination in the temporal example.

![Supplied observation and rule inputs, human confirmation, source-preserving binding, and unresolved-candidate deferral](figures/video-grounding-en.png)

Preparing and binding supplied scene inputs. Observations and rule content follow separate paths and are joined through human confirmation of applicability. Accepted inputs retain distinct observation and rule references; unresolved candidates are held without learning export. The 0.5 s wait is an illustrative supplied rule. The evaluated pipeline uses supplied synthetic inputs.

**1. Review supplied observations.** Use the CoC action context to review the supplied entities, zones, states, and timestamps. Link real-scene observations to supporting video segments; synthetic observations come from the environment generator. Uncertain or occluded evidence remains unresolved rather than being treated as confirmed clearance.

**2. Review the supplied rule.** Record the restriction and numerical parameters supplied by the experimental policy or reviewed rule evidence. For real scenes, the rule source may be an operating policy, operator instruction, or confirmed sign. Waiting durations and displacement tolerances require an explicit rule source; they are not invented from the scene or the CoC rationale.

**3. Confirm applicability.** Check that the rule applies to the observed entity, zone, and decision time. Distinguish what the video supports from what the rule requires, and disclose assumptions such as no reoccupation after clearance. For real scenes, reviewers confirm these bindings and the rule evidence before accepting the candidate.

**4. Bind the specification inputs.** Map the accepted restriction, comparisons, and bounds to EBLC rule fields, keeping scene states and event times as separate bindings. Retain references to both the observation and the rule. The resulting candidate proceeds to specification and checking; unresolved inputs remain unbound and are not exported as reviewed learning data.

These steps define input preparation and source binding. Automatic extraction by an LLM or perception model is outside this paper's scope. The evaluated pipeline starts from supplied observations and rules; it checks supported specification properties and evaluates candidate selection with the resulting CNL.

### 4. Implemented Transformations and Human Review

In the temporal synthetic experiment, the environment generator supplies the clearance time, while a supplied experimental rule sets the required waiting duration. The duration becomes an EBLC rule parameter; the clearance time and candidate action values are bound separately in verification queries. Automation structures and transforms these supplied conditions. Observed values and rule parameters remain separate inputs; specification checks do not establish their factual or normative validity.

For real-scene grounding, reviewers must confirm which observed entity and zone the constraint concerns, which events and clearance times the evidence supports, and whether the evidence meets the specified acceptance criteria. They must also establish rule applicability and the basis for timing parameters, modeling assumptions, and any initial activation and evidence history used by a lifecycle profile. These are grounding decisions that logical consistency checks cannot establish from evidence identifiers alone.

The implemented real-scene adapter supports one pinned scene18 development-review task. Target and zone bindings, event predicates, evidence acceptance, an independent action reference, and CNL review remain unresolved in that task; learning export is disabled. A conditional contract can still be checked under supplied inputs, but adopting it as reviewed real-scene learning data requires resolving those grounding and reference-review items. Deferral under incomplete evidence is a policy output, not an automatically established real-scene action label.

![Figure 2. Evidence-to-field mapping](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-005/figures/evidence-map-en.png)

Figure 2. Environmental clearance at 11.0 seconds binds a query variable, whereas the supplied 0.5-second duration becomes a contract field. No reoccupation is an assumption needed to connect these values through a temporal inequality. Derivation distinguishes these roles when constructing evidence-supported fields.

The next stage maps these inputs to EBLC fields; verification then checks the resulting permissions before CNL generation.


## C. Specifying Behavioral Constraints in EBLC

### 1. Scope and Elements

This stage represents an accepted constraint candidate and its evidence in a supported EBLC profile. Its output is a contract with defined interpretation; candidate values and verification verdicts are supplied in the next stage.

Evidence-Bound Lifecycle Contracts (EBLC) make the precedingbehavioral constraint explicit by recording its target, conditions, restricted action, persistence, release, and evidence. In the pedestrian example, the ego vehicle is the constrained actor and the conflict zone is the target. The condition is pedestrian occupancy of that zone, and the restricted action is vehicle entry. Persistence specifies that the restriction remains active until its release condition is met. Release requires confirmed clearance and, if stipulated by the supplied rule, completion of a minimum waiting duration. Evidence links identify the observations establishing occupancy or clearance and the rule defining the restriction and any required wait.

Evidence-Bound therefore denotes explicit links to the inputs on which conditions and rules depend; modeling assumptions define the scope of their interpretation. Lifecycle denotes activation, persistence, release, and, where required, reactivation. This paper uses these organizing principles and implemented restricted profiles, rather than assuming a language covering every traffic situation.

Table M2 summarizes these elements and their temporal instantiation.

**Table M2. EBLC elements and their temporal instantiation**

| Element | Specification role | Temporal instantiation |
|---|---|---|
| Subject and target | Whose action is restricted, and with respect to what? | Ego and pedestrian conflict zone |
| Scope | Situation and model of interpretation | Single clearance transition without reoccupation |
| Action restriction | What is disallowed? | Entry before release conditions hold |
| Persistence and release | When does the restriction persist or end? | Required duration following clearance |
| Time and units | Instants, durations, and boundaries | Integer milliseconds; inclusive threshold |
| Evidence and version | Rule sources and interpretation | Rule references and profile version |

The qualitative profile additionally represents event truth, evidence validity, initial activation, and a policy for combining obligations. These define how uncertain evidence is interpreted; they are distinct from the single-clearance temporal profile used in the primary learning experiment.

### 2. Contract Definition and Interpretation

We use $C = (s, z, \Sigma, O, E, V)$ to explain the profile organization: $s$ denotes the actor, $z$ the target or zone, $\Sigma$ the scope and modeling assumptions, $O$ the set of restrictive obligations, $E$ the observation and rule evidence links, and $V$ the interpretation version. This is explanatory notation, not a new six-field JSON schema. Actual serialization follows the restricted profile in Code Box 1.

An obligation is interpreted through its activation condition, persistence and release rules, restricted action, and any required initial state. The temporal profile compresses these into a single clearance time and a waiting duration. The qualitative profile updates activation from evidence and the previous state at each decision step. Assumptions and state variables from different profiles are not interchangeable.

Let $h_t$ denote the supplied evidence and state history through decision step $t$, and $a$ a current action candidate. The meaning of a contract is its admissible candidate set $A_C(h_t)$. Membership means compatibility with the stated conditions and restrictions. Subscript $t$ identifies the decision step, and $C$ identifies the contract. Multiple obligations combine their admissible sets by intersection, requiring all applicable restrictions to hold. The qualitative profile also imposes an entry policy requiring current clearance evidence. Previous inactivity is therefore distinct from current entry permission.

An independent objective selects among admissible candidates. Deferral and entry after sufficient waiting may both be permitted while receiving different progress scores. Separating admissibility from optimization prevents interpreting compliance as optimality.

### 3. Temporal Syntax and Semantics

The temporal profile records the actor, target zone, occupancy restriction, required wait, unit, assumption, and rule sources. Code Box 1 shows the serialized contract for a supplied 0.5-second rule.

**Code Box 1. Actual generated temporal contract JSON**

The input is a supplied 0.5-second waiting rule; the output is a contract containing its target, release condition, and assumptions. Line numbers refer to positions within this box.

```json
{
  "version": "supplied-temporal-eblc-profile-v0.1",
  "subject": "ego",
  "target": "pedestrian_conflict_zone",
  "hold": "NO_ENTRY_WHILE_OCCUPIED",
  "release_clear_ms": 500,
  "time_unit": "ms",
  "source_kind": "SUPPLIED_SYNTHETIC_RULE",
  "assumption": "SINGLE_CLEAR_TRANSITION_NO_REOCCUPATION",
  "source_refs": [
    "Project01/temporal_guard_world.py::_guard",
    "paper1-method-preservation-v0.1"
  ]
}
```

The `subject` and `target` identify the actor and restricted zone. The `hold` field specifies no entry during occupancy; `release_clear_ms` specifies waiting after clearance. The `assumption` permits one occupied-to-clear transition without reoccupation, so one clearance instant and an elapsed duration can represent continuous clearance. In Code Box 1, lines 2–5 identify version and restriction, lines 6–7 duration and unit, and lines 8–13 the assumption and sources.

For the temporal restriction, let $\tau_{\mathrm{ms}}$ denote environmental clearance time `clear_ms`, $u_{\mathrm{ms}}$ candidate entry time `entry_ms`, $\Delta_{\mathrm{ms}}$ the contract duration `release_clear_ms`, and $e$ the Boolean candidate indicator `enters`. The subscript ms denotes integer milliseconds. Both $\tau_{\mathrm{ms}}$ and $u_{\mathrm{ms}}$ are instants, whereas $\Delta_{\mathrm{ms}}$ is a duration. The entry restriction is:

`enters → entry_ms ≥ clear_ms + release_clear_ms`

The temporal admissibility predicate is equivalently $P_C=\neg e\lor(u_{\mathrm{ms}}\geq\tau_{\mathrm{ms}}+\Delta_{\mathrm{ms}})$. Thus, clearance alone does not establish that the required waiting duration has elapsed.

Code Box 1 contains the rule parameters, not a candidate's action values. Core lowering declares `enters`, `clear_ms`, and `entry_ms`; each verification query assigns the environment and candidate values separately. In particular, `enters = false` denotes a non-entering candidate, not a fixed contract field. Such a candidate satisfies this entry implication; its utility is evaluated by the separate objective.

The other numerical profiles store each bound under `limits` as `field/op/unit/ticks`: the restricted candidate attribute, comparison operator, external unit, and integer bound. After unit checking, `scale = 1000` represents values in thousandths of that external unit, rather than converting every quantity to milliseconds. For example, a deceleration bound of $5.8\,\mathrm{m/s^{2}}$ is stored as 5800 ticks. Candidate measurements are bound separately during verification.

### 4. Qualitative Lifecycle Semantics

The qualitative profile defines the interpretation of an obligation j at decision step t using condition status `truth[j,t]`, evidence acceptance `valid[j,t]`, and Boolean obligation state `active[j,t]`. Truth values are TRUE, FALSE, UNKNOWN, and CONFLICT. FALSE means confirmed resolution of the restricting condition, not merely a missing observation. Code Box 2 maps the current status and evidence validity, together with previous activation, to the current obligation state; `active` is not a direct copy of `truth`.

**Code Box 2. Pseudocode for evidence-based state updates**

Inputs are the current truth value and evidence validity for obligation j, together with previous activation; the output is current activation. This is explanatory pseudocode, not a verbatim source excerpt.

```text
on[j,t] = valid[j,t] AND (truth[j,t] = TRUE)
clear[j,t] = valid[j,t] AND (truth[j,t] = FALSE)
active[j,t] = TRUE,             if on[j,t]
              FALSE,           else if clear[j,t]
              previous_active, otherwise
```

Lines 1–2 define activation evidence `on` as valid TRUE and clearance evidence `clear` as valid FALSE. Lines 3–4 activate or release the obligation; line 5 retains its previous state for UNKNOWN, CONFLICT, or invalid evidence. At the first decision, `previous_active` is the supplied `prior_active`; subsequently it is the preceding step's `active`. These are interpretation rules relating evidence, obligation state, and action restrictions, not instructions about the solver's internal execution order.

![Figure 3. Obligation transitions and entry permission](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-005/figures/lifecycle-en.png)

Figure 3. (a) shows the state transitions of an individual obligation j; (b) combines all obligations' clearance conditions to determine entry permission. Solid arrows denote transitions or state retention; dashed arrows carry current clear values. The release condition in (a) and its corresponding input in (b) use the same evidence-derived value, combined with other obligations' clear values by AND. Panel (b) is neither a third state nor a nested state of (a). Because inactivity includes both initial inactivity and release, permission depends on current clearance of every obligation, not inactivity alone.

Figure 3 connects obligation state to the separate entry policy: `entry_permitted[t] = AND_j clear[j,t]`. Entry requires current valid clearance for every declared obligation. Previous inactivity alone does not permit entry when current clearance is unconfirmed. Starting from inactivity, valid TRUE → UNKNOWN → FALSE → TRUE yields active → active → inactive → active: UNKNOWN retains the active restriction, FALSE releases it, and a later TRUE reactivates it. Entry is permitted only at the third decision in this illustration, where deferral remains allowed.

Unknown, conflicting, or invalid evidence sets `review_required`. Evidence UNKNOWN and CONFLICT differ from a solver's UNKNOWN result, which means it could not decide a query. This subsection defines state interpretation; the separate lifecycle checks and their supplied-history scope are reported in the verification subsection.

### 5. Running Temporal Specification Example

This example maps original CoC, a supplied clearance observation, and an explicit waiting rule to the temporal contract and its query inputs. Original CoC reads “Yield to the crossing pedestrian, then proceed through the intersection.” Clearance occurs at 11.0 seconds; the rule requires 0.5 or 1.5 seconds of additional clearance. The duration is a supplied experimental condition, not inferred from CoC or asserted as a universal traffic-law requirement. We compare four hypothetical action candidates A–D in Table M3; three specify entry times and one defers entry.

**Table M3. Action-candidate admissibility under alternative waiting requirements**

| Candidate | Entry time | Assigned utility score | 0.5-second wait | 1.5-second wait |
|---|---|---|---|---|
| A | 10.5s | 110 | Violates | Violates |
| B | 11.5s | 100 | Admissible; reference action | Violates |
| C | 12.5s | 85 | Admissible | Admissible; reference action |
| D | No entry | 0 | Admissible | Admissible |

Table M3 presents a generated data instance, not observed model predictions. The generator assigns synthetic utility scores of 110, 100, 85, and 0 to the ordered candidate templates; these are not computed from measured distance or speed and do not enter the SMT restriction. Candidate B (11.5-second entry) is admissible under the 0.5-second rule but excluded under the 1.5-second rule. Candidate C (12.5-second entry) is admissible under both, and candidate D (deferral) satisfies both restrictions with zero utility.

Here, `reference action` denotes the highest-utility admissible candidate: B under the 0.5-second rule and C under the 1.5-second rule. The assigned scores provide an independent selection objective; they do not determine admissibility. The next subsection checks these permission conditions through logical queries. CNL generation later shows their expression in the augmented CoC, and the experimental section describes reference-label construction and training.

### 6. Why Use an EBLC Profile?

JSON specifies a serialization structure; by itself it does not assign lifecycle semantics, define the interpretation of unknown evidence, or establish what a generated sentence means. General temporal logics can express many of these conditions, and hand-written rules can implement them. EBLC is not claimed to be more expressive than those alternatives. Its role here is to fix a domain-specific contract between evidence fields, interpretation rules, supported Core lowering, and model-facing language. For example, `release_clear_ms` denotes a duration rather than an event time, a `ge` bound is inclusive, and `source_refs` records provenance rather than a model answer.

The contribution is thus an explicit development interface with checkable mappings, not the invention of implication, JSON, or SMT. Each implemented profile has a validator, logical interpretation, and renderer; unsupported combinations are rejected. The experiments evaluate the utility and checks of this path, not superiority over an equally specified JSON-to-SMT system. A bare schema would become an equivalent engineering alternative only after supplying the corresponding semantics, lowering, provenance policy, and language mapping.


## D. Verifying EBLC Specifications

### 1. Verification Purpose and Input Checks

Before rendering a contract as CNL for CoC augmentation, verification checks whether its executable representation rejects prohibited candidates while retaining intended permissions. This concerns the contract under supplied inputs and assumptions. It does not formally prove the original CoC or the combined natural-language text, factual scene interpretation, or vehicle safety.

Verification requires semantic input binding and logical queries. Subject, zone, event time, and applicable duration must refer to the same case; contracts must satisfy supported version, field, and unit requirements. Evidence identifiers enable traceability but do not prove factual truth. Unbound fields remain distinct from reviewer-confirmed scene bindings: syntax acceptance alone does not turn a conditional contract into reviewed learning data.

The temporal validator checks the supported version and fixed field combinations. Supported durations are 500, 1500, 800, and 1800ms; the primary expanded learning dataset uses 500 and 1500ms. This structural profile check precedes logical queries and does not itself establish candidate admissibility. Arbitrary JSON is not accepted as a general contract.

### 2. Core Lowering and Query Inputs

To enable SMT checking, EBLC temporal contracts are first translated into Core, an intermediate representation of typed variables and logical clauses. The lowering declares Boolean `enters` and integer `clear_ms` and `entry_ms`, and embeds `release_clear_ms` as an integer constant. Types are checked before SMT compilation; candidate values are assigned in subsequent queries as described in the temporal specification.

Time is represented by integer millisecond counts with the dimensionless Core unit marker `1`; 11000 counts mean 11.0 seconds under this profile. Variables are time-invariant and the clause is enforced initially, so a query checks fixed environment and candidate values rather than a stepwise vehicle trajectory. The configured `horizon = 2` bounds the logical model; it is not two seconds of physical driving verification.

### 3. Properties and Queries

Table M3 shows the permissions implied by the waiting rules; Table M5 specifies how consistency, restriction enforcement, release boundaries, and permissibility are checked. Base SAT establishes that a satisfying variable assignment exists, but this assignment may simply represent non-entry. We therefore separately check whether entry is feasible at and after release, avoiding a specification that admits deferral while excluding all entry.

The early-entry query checks a safety property within the encoded model: entry must not precede the required release time. SAT queries at and after release establish entry feasibility. They do not establish liveness, which would require eventual progress: deferral remains permitted. Whether a learned VLM actually selects a progress-making candidate is evaluated separately.

For the concrete boundary queries in Table M5, clearance is 11000ms and the wait is 500ms. Entering queries set `enters = true`; the deferral query sets it to false.

**Table M5. Properties, verification queries, and expected verdicts**

| Property | Query | Expected | Interpretation |
|---|---|---|---|
| Consistency | Base contract | SAT | A satisfying case exists |
| Restriction | Entry earlier than release | UNSAT | Early entry and contract are incompatible |
| Before boundary | Entry at 11.499s; wait 0.5s | UNSAT | Entry just before release is excluded |
| At boundary | Entry at 11.500s; wait 0.5s | SAT | Equality is permitted |
| After boundary | Entry at 11.501s; wait 0.5s | SAT | Entry after release is feasible |
| Deferral | enters is false | SAT | Entry is not forced |

The symbolic restriction query searches for an entering assignment with `entry_ms < clear_ms + release_clear_ms`, without fixing both time variables. UNSAT excludes such a counterexample under the encoded rule and assumptions. The concrete queries test 11499, 11500, and 11501ms: early entry must be UNSAT, while the inclusive boundary and later entry must be SAT. A mistaken strict comparison would reject 11500ms; an omitted waiting condition would admit premature entry. These are illustrative errors detectable by unexpected verdicts, not claims that those errors occurred in the current implementation.

Candidate-query verdicts are also compared with independently implemented integer environmental rules. An expected UNSAT result is the intended rejection of a hypothetical candidate, not evidence of an observed driving violation. Unexpected SAT or UNSAT and solver UNKNOWN require review; checking only permitted candidates would miss rules that also admit prohibited candidates. Concrete-case agreement and symbolic counterexample exclusion have distinct scopes, neither of which validates video evidence or the adequacy of a supplied waiting rule.

The six manuscript queries were executed for both 500ms and 1500ms contracts, yielding 12 matching verdicts. The existing bridge's 100 queries were rerun separately. These are archived specification checks, not new learning-effect evidence. Query records retain expected and observed results and actual SMT-LIB output for reproducibility.

### 4. SMT Representation and Interpretation

The following readable SMT-LIB example expresses the core 0.5-second restriction. It is an explanatory representation, not the entire compiler output, which is retained in separate query files.

**Code Box 3. Executable SMT-LIB example comparing early and boundary entry**

Inputs are the contract duration and clearance at 11000ms. Each candidate time is fixed in turn to query compatibility with the contract.

```text
(declare-const enters Bool)
(declare-const entry_ms Int)
(declare-const clear_ms Int)
(assert (= clear_ms 11000))
(assert (=> enters (>= entry_ms (+ clear_ms 500))))
(assert enters)
(push)
(assert (= entry_ms 11499))
(check-sat) ; unsat
(pop)
(push)
(assert (= entry_ms 11500))
(check-sat) ; sat
(pop)
```

The first UNSAT verdict indicates incompatibility of early entry with the specification, not a defective specification. The second SAT verdict indicates compatibility of the selected entry. Neither includes optimality or real-world safety. UNKNOWN or unexpected verdicts are not accepted as successful verification. Structural checks, scene binding, logical verification, and CNL correspondence serve different roles.

Lines 1–3 of Code Box 3 declare types; line 4 binds environmental clearance and line 5 states the restriction. Line 6 excludes satisfying the query through non-entry. Lines 7–10 temporarily add 11499ms, obtain UNSAT, and remove that candidate condition. Lines 11–14 add 11500ms to the same base contract and obtain SAT. The push/pop scopes prevent both candidate conditions from remaining simultaneously and causing an artificial contradiction.

### 5. Lifecycle Checks and Their Scope

We check whether an obligation stays active, is released, and becomes active again according to the specified rules. The initial state is supplied through `prior_active`. At each later step, the state is updated using the previous `active` value and the current evidence.

These checks use specified initial states and constructed evidence sequences. UNKNOWN or invalid clearance evidence leaves the previous state unchanged. Valid FALSE releases the obligation, while valid TRUE activates it.

For example, if an obligation was active and the current evidence is UNKNOWN, it must remain active. Adding a condition that it is now inactive must therefore return UNSAT. This checks the specified update rule; it does not show that a real scene’s history was correctly observed.

The archived qualitative run contains 25 queries matching their expected verdicts. These checks establish the stated behavior under the supplied initial states and evidence sequences; they do not establish that those inputs were correctly recovered from real-scene video. The primary temporal learning evaluation uses `clear_ms`, `entry_ms`, and `enters` under the no-reoccupation assumption and does not track previous activation. In the qualitative profile, activation depends on history while entry permission requires current clearance of every obligation. Neither profile guarantees eventual entry.


## E. CNL Generation and CoC Augmentation

### 1. Generating Sentences from Verified Specifications

CNL is generated from checked fields through fixed sentence rules. The temporal renderer accepts structurally validated contracts and maps zone and duration to text. It does not itself invoke the solver; specification verification precedes rendering. Candidate labels, reference actions, and progress scores are not generator arguments.

**Code Box 4. Verbatim excerpt of the CNL generator**

Code Box 4 reproduces the temporal contract renderer used in the experiments. Input raw is a temporal contract; the return value contains two sentences. Numbers count logical source lines; long lines wrap within the box.

```python
def render(raw):
    validate(raw)
    # Render only validated contract fields, never scene target/candidate/answer.
    return ('Do not enter the pedestrian conflict zone while it is occupied. '
            f'Enter only after the zone has remained clear for at least {raw["release_clear_ms"]/1000:.1f} s.')
```

Line 2 requires an exact match to a supported contract. Since validation also fixes the target and restriction type, line 4 can emit a constant zone phrase. Line 5 converts milliseconds to seconds with one decimal place, exactly representing the currently supported durations. The function neither invokes the solver nor selects a target action. Other targets or arbitrary precision would require a separate extension.

Actual output for the 0.5-second contract is:

> Do not enter the pedestrian conflict zone while it is occupied. Enter only after the zone has remained clear for at least 0.5 s.

Figure 4 shows how the EBLC specification maps to the two CNL sentences above. The first sentence identifies the zone and prohibits entry while it is occupied. The second states the clearance condition and required waiting duration. “At least” includes the boundary value, and “only after” states a necessary condition for entry; it does not require entry. The conversion maps 500ms to 0.5s and 1500ms to 1.5s. This correspondence applies to supported durations under the single-clearance, no-reoccupation assumption.

![Figure 4. Specification-to-CNL correspondence](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-005/figures/cnl-map-en.png)

Figure 4. Target and restriction map to the first sentence; release duration and the inclusive boundary map to the second. Original CoC and CNL enter the model together, while source and version metadata remain separately traceable. Colors distinguish mappings, not additional levels of verification.

### 2. Scope of Semantic Correspondence

Generation preserves target, negation, conditional direction, value, and unit. Omitting “at least” or replacing “enter only after” with a requirement to enter after clearance would change admissibility. Fixed field mappings make these relationships explicit and inspectable.

Not all metadata appears in model-facing sentences. Versions and source references remain traceability metadata; CNL conveys action-relevant conditions. Modeling assumptions are specified in the environment and task definition. The claim is correspondence of action restrictions within that context, not literal one-to-one rendering of every JSON field. Freely rewritten sentences or additional profiles require separate semantic review.

### 3. Combining CNL with Learning Inputs

Original CoC provides an action rationale, and CNL supplies additional behavioral conditions. They are combined without replacing CoC with a specification. Table M6 separates the original CoC from the added CNL; the model-facing text concatenates them in that order. Temporal rows reproduce synthetic training text, whereas the STOP row summarizes and translates the core of a real-scene development output.

**Table M6. Original CoC and added constraint sentences**

| Example | Original CoC | Added CNL |
|---|---|---|
| Pedestrian yielding, 0.5-second rule | Yield to the crossing pedestrian, then proceed through the intersection. | Do not enter the pedestrian conflict zone while it is occupied. Enter only after the zone has remained clear for at least 0.5 s. |
| Pedestrian yielding, 1.5-second rule | Yield to the crossing pedestrian, then proceed through the intersection. | Do not enter the pedestrian conflict zone while it is occupied. Enter only after the zone has remained clear for at least 1.5 s. |
| Worker’s STOP sign: illustrative real-scene example | Stop at the stop sign held by the construction worker for the one-way alternating traffic zone ahead. | While the confirmed stop instruction applies to ego at the current decision, do not start or accelerate even if motion state is unknown. This does not prohibit deceleration intended to stop or continued waiting; instruction clearance is not established. |

The first two rows pair different waiting rules for the same task, not different scene categories. If the zone clears at 6.0 s, entry at 6.5 s meets the 0.5-second condition but not the 1.5-second condition. CNL thus distinguishes prohibition and release conditions absent from the shared CoC; the durations are supplied experimental rules. The STOP row expresses a prohibition common to moving and stationary states and is separate from the main synthetic performance experiment. Adding a constraint does not confirm every factual claim in the original CoC. In the worker's STOP-sign example, the original claim about a red light remained unconfirmed. The added constraint was based on a separately confirmed STOP instruction from the worker.

For the 0.5-second temporal example, the complete augmented requirement text is:

> Yield to the crossing pedestrian, then proceed through the intersection. Do not enter the pedestrian conflict zone while it is occupied. Enter only after the zone has remained clear for at least 0.5 s.

The first sentence is the original CoC; the last two are generated restrictions. Clearance at 11.0 seconds is separate environmental information, so this text conveys a rule rather than specifying the answer “enter at 11.5 seconds.”

The generated sentences follow the existing rationale in `Requirement CoC`, before candidate descriptions and the selection instruction. Static records construct `rich_coc_text = COC_TEXT + " " + CNL`; maneuver records append `constraint_text` to the CoC requirement. EBLC, provenance, query verdicts, candidates, reference labels, image references, and splits remain in separate traceability records. Neither the reference label nor SAT/UNSAT is inserted as an answer hint.

The image and action candidates accompany this text, while a separate reference calculation supplies the target label. To evaluate constraint augmentation, we compare three model-input conditions: original CoC alone (P0), CoC with the existing natural-language constraint (P1), and CoC with EBLC-derived CNL (P2). Both P1 and P2 are compared primarily with P0. Section V describes the experiment. Raw EBLC JSON and solver verdicts are not supplied as answer hints.



## F. Task-to-Field-to-Verdict Summary

Table M1 shows how supplied rules for the six evaluated tasks become EBLC fields, logical conditions, CNL, and candidate judgments. The examples come from archived test contracts; the temporal row uses the boundary query described above. They illustrate implemented specifications, rather than six independently collected road videos. The constraint fields record supplied rule limits, not values inferred from pixels. These fields are compiled into logical conditions during verification, while candidate measurements and completion or entry flags are supplied separately. The same contract fields are also used to generate CNL.

Let $q$ denote `completes`, $e$ denote `enters`, and $\widehat{x}$ denote a candidate measurement scaled by 1000. Each non-temporal Core clause is $q\Rightarrow(\widehat{x}\ \mathrm{op}\ b)$, where $b$ is the stored integer `ticks`. For stopping, three clauses are conjoined. Static candidates all complete; noncompletion in a maneuver is nonviolating but does not count as goal completion. The generated CNL conveys numeric bounds but does not separately render the Core exemption for noncompletion. Correspondence of bounds for goal-completing candidates is therefore distinguished from whole-contract equivalence over noncompleting behavior; the latter is not established here. The profile checks stored candidate summaries, not continuous trajectories.

**Table M1. Executed task-to-verdict mappings; CNL cells quote generated clauses**

| Task | Constraint fields | Actual logical condition | Generated CNL | Candidate judgment |
|---|---|---|---|---|
| Maximum speed | `speed/le/m/s/4400` | $q\Rightarrow\widehat{v}\leq4400$ | The candidate's maximum speed must be at most 4.4 m/s. | A: 6.0 m/s, UNSAT; B: 2.8 m/s, SAT |
| Minimum clearance | `clearance/ge/m/2000` | $q\Rightarrow\widehat{d}\geq2000$ | The candidate's minimum obstacle clearance must be at least 2 m. | A: 0.9 m, UNSAT; B: 3.1 m, SAT |
| Minimum entry delay | `entry_delay/ge/s/2500` | $q\Rightarrow\widehat{u}\geq2500$ | The candidate's intersection entry time from now must be at least 2.5 s. | A: 0.9 s, UNSAT; B: 4.1 s, SAT |
| Temporal clearance | `release_clear_ms=500` | $e\Rightarrow u_{\mathrm{ms}}\geq11000+500$ | Enter only after the zone has remained clear for at least 0.5 s. | 11499 ms: UNSAT; 11500 ms: SAT |
| Stopping | `stop_offset_m`, `peak_decel`, `peak_jerk`; bounds 0, 5800, 7400 | $q\Rightarrow(\widehat{o}\leq0\land\widehat{a}\leq5800\land\widehat{j}\leq7400)$ | Stop at or before the stop line (stop offset at most 0 m). | C beyond line: UNSAT; D within all bounds: SAT and preferred |
| Lane change | `min_gap_m/ge/m/5800` | $q\Rightarrow\widehat{g}\geq5800$ | The candidate's minimum gap during the lane change must be at least 5.8 m. | D: UNSAT; A: SAT and preferred; C: SAT but incomplete |

For stopping, the two remaining generated clauses are “The candidate's peak deceleration must be at most $5.8\,\mathrm{m/s^{2}}$.” and “The candidate's peak jerk must be at most $7.4\,\mathrm{m/s^{3}}$.” Thus the table abbreviates the CNL display, not the checked contract. Here $o$ is signed stop offset, $a$ peak deceleration, $j$ peak jerk, $g$ minimum lane-change gap, $v$ maximum speed, $d$ minimum obstacle clearance, and $u$ entry delay. Temporal clearance differs from a fixed delay from now: it binds an observed clearance instant before adding the required wait.

For each action candidate, we check whether its supplied values satisfy the compiled contract. The solver combines the contract with assignments of candidate measurements and the completion flag, or the entry flag in the temporal profile. We write this query as $\Phi_C\land B(a)$, where $\Phi_C$ is the contract's logical representation and $B(a)$ specifies the candidate inputs. SAT means compatible with the encoded contract; UNSAT means incompatible.

For example, the supplied maximum-speed rule of 4.4 m/s is stored as `speed/le/m/s/4400`. With a scale of 1000, the logical condition is $q\Rightarrow\widehat{v}\leq4400$. For a candidate that completes the task, 6.0 m/s is rejected (UNSAT), while 2.8 m/s is permitted (SAT). In the temporal row, `release_clear_ms=500` is a contract field; `clear_ms=11000` is a separate environmental query input.

A reference program separately applies the same supplied task rules to identify allowed candidates. It selects the allowed candidate with the highest progress score as the reference answer. Accuracy measures whether the learned model selects that answer. A violation occurs when the model selects a prohibited candidate. For example, waiting and entering after the required delay may both be allowed, but waiting has lower progress. A SAT choice can therefore be an incorrect answer without violating the contract.

Comparing the reference program's admissibility judgments with SMT verdicts checks whether the two implementations agree. Both use the same supplied rules and assumptions, so agreement does not independently establish safety on real roads.

The experimental section follows the same order: task-wise accuracy and violations, response to changed contracts, and specification/CNL quality. Detailed per-candidate records and unsupported-error cases remain in the supplement.

## Implementation and Example Evidence

These links provide reproducibility evidence for manuscript review, separate from external related-work citations. They will connect to code and data availability and supplementary material in the integrated manuscript.

- [Temporal contracts, Core lowering, verification, and CNL generation](../../experiments/paper1_cnl_learning/temporal_preservation.py)
- [Qualitative contract parsing and lifecycle semantics](../../../../platforms/eblc-bcv/src/guard_synth_eblc/action_contract.py)
- [Learning inputs and independent reference calculation](../../experiments/paper1_cnl_learning/temporal_training_data.py)
- [Restricted real-scene adapter](../../src/guard_synth/qualitative_scene_contract.py)
- [Synthetic training records for the before-and-after comparison](../../artifacts/public/paper1-method-preservation-001/temporal-training-data-2026-09-29-001/train_paired.jsonl)
- [Real-scene development records for the before-and-after comparison](../../artifacts/restricted/guardsynth-eblc-learning-001/speed-development-packaging-2026-09-29-003/l3_admitted_train.jsonl)
- [Executed manuscript queries and results](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-001/manuscript_examples.json)
- [Two example learning-input records](../../artifacts/public/paper1-method-preservation-001/methodology-2026-09-30-001/learning_input_examples.json)

The internal temporal query archive is `methodology-2026-09-30-001/manuscript_examples.json`; the qualitative archive is `scene18-action-contract-2026-09-08-001`. These source records identify expected and observed verdicts and executable query output. Public code and data availability must be finalized during submission preparation; these internal identifiers are not manuscript prose.
