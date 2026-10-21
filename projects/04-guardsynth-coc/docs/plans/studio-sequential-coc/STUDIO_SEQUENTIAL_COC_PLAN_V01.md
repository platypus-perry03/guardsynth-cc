# Studio Sequential CoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Studio에서 VLM의 실제 행동 CoC와 제약을 별도로 만들고, 상태를 넘기는 연속 EBLC 검증을 검토한다.

**Architecture:** 프로젝트 소유 sequence checker와 앱 소유 workflow를 분리한다. 기존 revision/job/provider/권한 체계를 재사용한다.

**Tech Stack:** Python stdlib SQLite/HTTP, EBLC Core IR/Z3, JavaScript, unittest/Playwright.

**Spec:** ../../requirements/STUDIO_SEQUENTIAL_COC_REQUIREMENTS_V01.md, ../../designs/STUDIO_SEQUENTIAL_COC_DESIGN_V01.md

## Global Constraints

- project_id=guardsynth-coc; reusable EBLC implementation remains platforms/eblc-bcv.
- No paid model calls in acceptance tests; production generation runs only by button.
- Existing revisions/approvals/budget preserved; DRAFT training_eligible=false.
- Maximum 200 moments, 16 candidates per moment, 64 stable conditions; only t0-or-earlier evidence.

## Review Focus

- FALSE without evidence and occlusion must retain old active obligation.
- Empty or unreviewed generated output must not become PASS.
- Catalog and earlier moment changes must invalidate dependent generation and verification.
- Malformed model output, fabricated source IDs and identity drift must be rejected or visibly held.
- Navigation while editing must preserve drafts and expose version conflicts.

### Task 1: EBLC sequence profile

Files: create projects/04-guardsynth-coc/src/guard_synth/studio_sequence.py; create apps/guardsynth_studio/tests/test_sequence.py.
Interfaces: candidate_schema(task), validate_candidate(task,data,frame_ids,source_ids), verify_sequence(moments,catalog).
- [x] Write tests: retained condition at scene 4, missing release evidence, reactivation, scope end, rule conflict, ID drift and catalog coverage.
- [x] Run tests and observe missing module failure.
- [x] Implement strict schemas, bounded ledger, deterministic Core IR and genuine SMT queries with trace mapping.
- [x] Run checker tests, assert literal expected contradictions/unknown/pending states.

### Task 2: Durable workflow and provider

Files: create apps/guardsynth_studio/sequence.py; modify store.py, service.py, jobs.py, provider.py, task.py, server.py.
Interfaces: enqueue_sequence(service,...), sequence_view(service,extraction), catalog_edit(...), sequence_snapshot(...).
- [x] Add failing tests for causal two-stage inputs, unchanged acceptance, downstream staleness and immutable result/export snapshots.
- [x] Extend new component dependencies and approval gates; integrate new VLM job types with existing call reservation.
- [x] Add queued CPU sequence checks and snapshot-bound draft download; catalog revision CAS.
- [x] Run workflow and existing provider tests; invalid outputs must never install.

### Task 3: Studio review panel

Files: create static/sequence.js; modify index.html, app.js, style.css, tests/test_http_browser.py, README.md.
Interfaces: studio:moment event renders new panel; edits use existing queue/flush/approve.
- [x] Add browser test for generated basic CoC, acceptance checkbox, constraint cards, stateful check table and download.
- [x] Implement simple aligned Korean controls, candidate explanation/unknown handling and shared source catalog editor.
- [x] Verify changing moments flushes drafts and input changes make results stale; old screens remain usable.
- [x] Run complete Studio suite, JS syntax, naming and scoped diff checks.

### Task 4: Review and local deployment

- [x] Request fresh whole-change review using requesting-code-review; fix concrete findings and rerun affected checks.
- [x] Copy only changed task files to main workspace with baseline SHA guard; retain unrelated work.
- [x] Restart existing loopback Studio with same persistent run/config after DB backup; verify health/static/backend.
- [x] Record tested scope, paid calls=0, limits and accessible documents in implementation report.

Execution authorization: user explicitly requested requirements/design followed by implementation; execute inline in current session.
No commit/merge requested. Progress ledger is scratch state, not a promoted project report.

## 2026-10-04: Tested generation and verification integration

Implementation authorized by user: “coc, 제약사항 개선도 연결...나머지 반영”.

Global constraints: preserve five stages, model original/revisions/approvals and paid budget. No acceptance-test paid calls. CoC/constraints requests use immediately preceding and current frames (at most two), causal CAN, anonymous entity slots plus confirmed previous IDs, closed evidence refs. Prior condition definitions are immutable; state is carried as a bounded summary, not all old images. Logical checks and absent legal sources are separate. UNKNOWN, empty/unsupported constraints and partial coverage cannot inflate PASS. First unedited model-pair quality is captured once per generation pair/version and cannot be replaced by edits or approvals. Human corrections require explicit save/approval and re-verification; model drafts are never overwritten.

1. Structured profile -> verify: seven classes, targets/relations/pre/postconditions, binding and unsupported diagnostics; actual Core/Z3 contradictions, unknown-not-release and partial starts. Implement in project-owned studio_grounded_sequence.py, dispatch through studio_sequence.py. Output compiled/verified scenes retains moment_id/ordinal/status/codes, constraints/explanation/ledger, and review_items [{code,message,sources:[{moment_id,component,path,value,evidence_refs}]}]. PASS requires complete supported recorded-action check; source_status separately marks legal review.
2. App generation and snapshots -> verify: wire bound schemas and low reasoning into provider, two-frame CAN; prior scene context and summaries; late earlier annotations invalidate results. candidate_schema(task) now describes v2; candidate extraction/validation recognizes legacy saved payloads. Quality API in sequence_view quality {first_pass:{total,pass,contradiction,review_required,pass_rate},reviewed:{...},items:[...]} from original paired generations independently of user edits, grouped by moments and original generation identities, persisted first result. Explicit job buttons only.
3. Minimal review UI -> verify: filled structured CoC and constraint proposals editable next to model original, acceptance checkbox only unchanged; Korean labels and examples in expanded details; counterexamples show statements/evidence and links to correct moment/component/field. Existing five navigation stages remain. Original quality separate from reviewed quality and provenance.
4. Integration -> verify: existing regression suite and browser workflow, saved 100 actual structured points replayed offline without API calls; SHA-guarded copy into main, restart same local Studio preserving SQLite and config, verify health and UI.

Dependencies: profile exposes grounded_schema(task,context=None), validate_grounded(task,data,frame_ids,source_ids,context=None), compile_grounded_sequence(moments,catalog), verify_grounded_compiled(compiled), render_grounded_verified(compiled,verification). App passes whole v2 candidates (not legacy constraints-only projection). UI detects entities/new_definitions keys; verification review_items uses source pointers. Existing legacy objects remain explicitly legacy; no invented migration data.
