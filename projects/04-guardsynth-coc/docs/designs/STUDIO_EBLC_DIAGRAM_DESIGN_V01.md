# Studio EBLC Diagram Design v0.1

- Owner: `guardsynth-coc`
- Approved scope: per-constraint vertical diagrams and manual rolling navigation in Studio stage 3.

## Review layout

Keep a compact, scrollable list of all constraints above one selected card. Each list button shows its description and verification state. Previous/next buttons wrap through cards; keyboard arrows and horizontal touch swipes navigate manually. No timers or automatic navigation. Reset selection when changing moments and retain a stable condition ID within the same moment.

The card shows class, description, previous/current lifecycle state, then four vertically connected nodes: target/relation, activation, action effect/maintenance, release. Activation is an AND group and release an OR group in structured input. Preconditions and expected postconditions are expandable in the action node. Expected postconditions are expectations for the next observation, never asserted future facts. Condition release is not permission to drive: other constraints still apply.

## Data and semantics

Render only the selected scene's saved compiled EBLC and verification artifacts. No VLM call, model mutation, new solver query, or invented relation. Structured input uses stored definitions, typed entity references, and `states`; legacy input preserves lifecycle text and scope, marks entity relationships as unstructured, and reads previous/current `ledger` values. Use only the immediately preceding ordinal for continuity; a missing previous scene remains a partial start.

Show verified per-condition UNSAT as a contradiction. SAT alone does not clear scene-wide review findings; green appears only when the saved scene verification is PASS. Findings without a condition reference remain scene-wide. Stale EBLC or verification is visibly marked and is never displayed as current success. Empty and ungenerated results show explicit empty states; Core JSON remains available in collapsed details.

Use the compiled source map for a correction button, including inherited definitions from a preceding moment. For legacy definitions without source maps, link only when the condition exists in the current editable constraints. Never infer an edit location. Evidence references and rule-source IDs are available in details. Text uses DOM `textContent` and wraps within narrow panels.

## Verification

Browser acceptance covers actual two-scene compilation/verification, manual button/keyboard/swipe navigation and overview selection, narrow layout, carried unknown conditions, release, counterexample correction navigation, stale artifacts, empty states, and legacy text compatibility. Existing Studio tests must pass. Deployment preserves all annotation revisions, approvals, auth/provider configuration, and model call counts.
