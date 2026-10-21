# 인접 두 장면 CoC·제약 검증 예제

- project_id: `guardsynth-coc`
- subproject_id: `guardsynth-studio-sequential-coc`
- 기준일: 2026-10-03
- 결과: 5개 가상 사례를 기존 EBLC action lowering → Core → Z3로 실행. 통과 1, 모순 3, 확인 필요 1.
- 유료 모델 호출: 0회
- 범위: 두 시점, 가상으로 명시한 조건·정책·대상 연결. 실제 영상, 실제 인과 효과, 제어 안전성 인증이 아니다. Studio에 새 스키마를 구현한 결과도 아니다.

## 공통 대상과 제약

| 요소 | 정의 |
|---|---|
| 주체 | 자차 ego |
| 신호 | S1, 자차의 Z1/M1 직진 이동에 적용 |
| 교차 차량 | 차량 A, 해당 충돌 영역을 점유할 수 있는 대상 |
| 행동 대상 | 교차로 영역 Z1, 직진 이동 M1 |
| C_S: 통행 제어 제약 | 적용 신호가 적색이면 Z1/M1 진입 제한. 같은 적용 신호의 녹색 확인으로 해제 |
| C_A: 차량 상호작용 제약 | A가 해당 충돌 영역을 점유하면 Z1/M1 진입 제한. 같은 A의 해당 영역 이탈 확인으로 해제 |

합성 정책은 선언된 두 제한의 해제가 확인되어야 진입을 허용한다. 허용은 진입 의무가 아니고 DEFER_ENTRY는 정지 명령이 아니다. 이 예제에서는 녹화된 행동을 가상으로 HOLD 또는 ENTER로 지정하고, 진입 선택만 DEFER_ENTRY/ENTER_ZONE에 대응한다. 다른 주행 행동을 정지로 변환하지 않는다. 노란 신호, 추가 차량·보행자·우선권·물리 동역학은 이 예제 명세에 포함되지 않는다. 전체 위험의 완전성을 주장하지 않는다.

## 장면 1 — 모든 사례의 공통 이전 장면

> 자차는 적용 신호 S1이 적색이고 교차 차량 A가 충돌 영역에 있어, Z1 진입을 보류하며 정지 상태를 유지했다.

| 신호 | A의 점유 | 자차 위치·행동 | 다음 장면으로 전달할 요약 |
|---|---|---|---|
| 적색 | 확인됨 | Z1 밖 · 정지 유지 · 진입 보류 | C_S=ACTIVE, C_A=ACTIVE |

조건의 원인 대상은 S1/A이고 행동 대상은 Z1이다. 차량 A의 경로 관계는 교차이고, 현재 점유 여부는 별도의 시점별 관찰이다. 가상 입력은 선행 관찰 10.0/11.0초, 행동 10.1/11.1초, 후행 관찰 10.2/11.2초로 지정해 행동 후 관찰을 선행 이유로 사용하지 않는다. 객체·적용 방향과 관찰의 유효성은 예제에서 명시한 가정이다.

## 장면 2 — 사례별 CoC와 실제 판정

| 사례 | 장면 2 CoC | 현재 제약 상태/관찰 | 자차 행동·후행 상태 | 판정 |
|---|---|---|---|---|
| ① 해제 확인 후 진입 | 녹색 신호와 차량 A의 충돌 영역 이탈을 확인하여, 자차는 Z1의 직진 경로로 진입했다. | C_S 해제 · C_A 해제 | 진입 완료 기록 · Z1 안 관찰 | PASS |
| ② 미해제 조건과 진입 충돌 | 적용 신호가 녹색으로 바뀌어 자차는 Z1에 진입했다. 교차 차량 A는 여전히 해당 충돌 영역에 있다. | C_S 해제 · C_A 유지 | 진입 완료 기록 · Z1 안 관찰 | FAIL |
| ③ 관찰 미확인과 보류 | 적용 신호는 녹색이지만 차량 A가 가려져 이탈을 확인하지 못했다. 자차는 진입을 보류하며 정지 상태를 유지했다. | C_S 해제 · C_A 유지/현재 미확인 | 정지 유지 관찰 · 진입 보류 · Z1 밖 | REVIEW_REQUIRED |
| ④ 현재 목록에서 조건 생략 | 적용 신호가 녹색으로 바뀌어 자차는 Z1에 진입했다. | C_S 해제 · C_A 유지 | 진입 완료 기록 · Z1 안 관찰 | FAIL |
| ⑤ 후행 상태 불일치 | 녹색 신호와 차량 A의 이탈을 확인하여 자차가 Z1에 진입을 완료했다고 CoC에 기록했다. | C_S 해제 · C_A 해제 | 진입 완료 기록 · Z1 밖 관찰 | FAIL |

① 같은 적용 신호의 녹색과 같은 차량 A의 이탈을 확인해 두 제한을 해제한다. 기록된 진입과 진입 후 위치가 일치하므로 명시한 범위 안에서 통과한다.

② 신호 제한만 해제됐다. A의 현재 점유가 확인되어 C_A는 활성이고 진입과 충돌한다. 실제 충돌 사고를 증명한 것이 아니라 합성 진입 정책과 기록된 행동의 불일치다.

③ A가 보이지 않아 이탈을 확정하지 못한다. 이전 C_A 상태는 보존하고 현재 관찰을 UNKNOWN으로 둔다. 기록된 진입 보류와 계약은 SAT이지만, A의 현재 상태가 미확인이므로 전체 예제 판정은 REVIEW_REQUIRED다. 규칙이 지켜졌다고 실제 안전성을 인증하지 않는다.

④ 현재 제약 목록에는 C_S만 들어 있지만 C_A는 이전 요약에 남아 있다. 현재 A 점유 관찰과 결합해 정상 모델은 진입 모순을 잡는다. 후보 목록에서 조건을 생략한 것 자체가 오류는 아니다. 현재 목록만 보고 C_A를 지운 잘못된 모델은 SAT를 반환하지만, 유지 조건 보존 검사에서 INVALID_MODEL_MISSING_CARRY다.

⑤ 신호/차량 조건은 해제됐지만 CoC의 진입 완료 주장과 후행 위치 Z1 밖 관찰이 충돌한다. 이는 행동 주석·상태 전이 불일치 사례이며 실제 운전 위반을 확정하지 않는다.

## 검증 모델

가상 인터페이스는 zone=Z1, movement=M1로 고정한다. 기존 v0.1 action 계약은 단일 zone 프로파일이므로 임의의 entity/관계 그래프와 모든 상위 클래스를 이미 지원한다고 주장하지 않는다. Entity·movement 연결은 입력 sidecar에서 고정하고 C_S/C_A는 obligation의 target_entity_id와 predicate_id로 연결한다. 모델의 시간축은 t=0,1뿐이다.

```text
on(C,t)    = 관찰근거유효(C,t) AND 위험조건(C,t)=TRUE
clear(C,t) = 관찰근거유효(C,t) AND 위험조건(C,t)=FALSE
active(C,1)= on(C,1) ? TRUE : clear(C,1) ? FALSE : active(C,0)
active(C,t) → 해당 Z1/M1 진입 금지
진입 허용(t) = clear(C_S,t) AND clear(C_A,t)
진입 완료(t) → 진입 허용(t)
inside(Z1,1) = inside(Z1,0) OR 진입완료(1)
```

마지막 식은 이 예제의 제한된 정성 전이 명세다. 이전 위치는 Z1 밖이고 두 장면 사이의 입장 완료만 모델링하며, 되돌아 나오는 복합 이동이나 차량 동역학은 포함하지 않는다. 과거 전체 장면이나 미래 시간축을 펼치지 않는다. 조건·전이 모델에 관찰한 행동/현재 위치를 별도 질의로 넣어, 기본 명세의 SAT와 행동·후행 비교의 SAT/UNSAT를 구별한다.

| 사례 | 기본 조건 모델 | 행동·후행 비교 | 최종 판정 | 모델 실행 시간 |
|---|---|---|---|---|
| ① 해제 확인 후 진입 | SAT | SAT | PASS | 47.8 ms |
| ② 미해제 조건과 진입 충돌 | SAT | UNSAT | FAIL | 44.1 ms |
| ③ 관찰 미확인과 보류 | SAT | SAT | REVIEW_REQUIRED | 40.6 ms |
| ④ 현재 목록에서 조건 생략 | SAT | UNSAT | FAIL | 71.3 ms |
| ⑤ 후행 상태 불일치 | SAT | UNSAT | FAIL | 42.5 ms |

시간은 프로세스 시작·LLM 생성·영상 인식·UI·DB 비용을 제외한 모델 작성/형식 검사/컴파일/SMT/진단 시간이다. ④에는 잘못된 모델과의 비교 실행도 포함한다. 각 1회 실행이며 성능의 분포나 일반적인 최악 시간을 보장하지 않는다. 각 모델은 2시점·30개 펼친 변수로 제한했다. 모든 기본 조건 모델이 SAT이므로 행동 비교의 UNSAT를 원래 규칙들 자체의 모순과 혼동하지 않는다.

## 실제 UNSAT 근거

- ② 미해제 조건과 진입 충돌: `cross_a_evidence_1`, `cross_a_fact_1`, `cross_a_no_entry`, `cross_a_on`, `cross_a_transition`, `recorded_action_query`
- ④ 현재 목록에서 조건 생략: `cross_a_evidence_1`, `cross_a_fact_1`, `cross_a_no_entry`, `cross_a_on`, `cross_a_transition`, `recorded_action_query`
- ⑤ 후행 상태 불일치: `entry_completion_semantics`, `recorded_action_query`

UNSAT core는 실제 Z3 진단에서 나온 절 집합이며 최소 크기를 보장하지 않는다. ②·④는 A 점유 관찰·발동·유지·진입 제한과 행동 질의가 충돌한다. ⑤는 진입 완료 전이 의미와 행동/후행 관찰 질의가 충돌한다.

## 파일과 재현

- [전체 결과](RESULT.json), [모델별 결과 표](scenario_results.csv), [두 장면 CoC 비교 CSV](scene_comparison.csv).
- [통과 모델](s01_clear_and_enter/core_model.json), [통과하지 못한 모델](s02_active_and_enter/core_model.json).
- [통과 SMT 질의](s01_clear_and_enter/recorded_action.smt2), [실패 SMT 질의](s02_active_and_enter/recorded_action.smt2).
- 각 사례 폴더에 입력, action contract, Core, source map, symbol table, 질의 결과와 실제 UNSAT 근거가 있다.
- [조건 보존을 누락한 잘못된 모델](s04_local_omission/naive_core_without_carry.json)은 교육용 비교다. SAT를 정상 통과로 받아들이면 안 된다.
- [실행 스크립트](pair_scenario_probe.py), [환경과 소스 해시](RUN_MANIFEST.json). 기존 run을 덮어쓰지 않고 새로운 run ID로 실행한다.

```bash
PYTHONPATH=projects/04-guardsynth-coc/src:platforms/eblc-bcv/src:. runtime/alpamayo/ar1_venv/bin/python -B projects/04-guardsynth-coc/artifacts/intermediate/guardsynth-studio-sequential-coc-001/studio-pair-scenario-test-2026-10-03-002/pair_scenario_probe.py --output projects/04-guardsynth-coc/artifacts/intermediate/guardsynth-studio-sequential-coc-001/studio-pair-scenario-test-2026-10-03-003
```

001은 후행 관찰을 기본 모델에 섞어 진단이 혼합된 초기 구성 시도로 FAILED_MODEL_CONSTRUCTION을 기록했다. 002는 관찰을 질의로 분리해 위 예상 결과를 실제로 확인한 산출물이다. 제품 코드는 변경하지 않았다.
