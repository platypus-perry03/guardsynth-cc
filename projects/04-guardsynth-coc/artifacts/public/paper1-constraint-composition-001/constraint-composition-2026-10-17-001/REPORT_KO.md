# 조합 제약의 모순 검사

소유 프로젝트: `guardsynth-coc`

기존 보행자 진입·위치 유지 변환기와 플랫폼 SMT 컴파일러를 재사용한 합성 명세 평가다. 실제 사고 재현이나 주행 모델 재학습 실험이 아니다.

| 조합 | 사례 | 전체 SAT | 전체 UNSAT | 단독 검사로 발견 | 쌍별 검사로 발견 |
|---|---:|---:|---:|---:|---:|
| entry_deadline | 48 | 36 | 12 | 0 | 12 |
| hold_departure | 12 | 10 | 2 | 0 | 2 |
| speed_progress | 27 | 18 | 9 | 0 | 9 |
| three_way_timing | 36 | 24 | 12 | 0 | 0 |

## 서로 다른 출처의 자연어 명세와 정형 명세

출처 S1–S9는 프로토콜에 작성한 서로 다른 합성 문서다. 실제 법규·운영자 문서를 수집한 결과가 아니다. 아래 문장은 공급된 구조화 매개변수를 설명하기 위한 템플릿이며 자동 자연어 해석·검증 결과가 아니다. 시간은 별도 표시가 없으면 ms, 좌표는 mm, 속도는 mm/s다.

### entry_deadline: entry_deadline-000

고정 맥락: Supplied synthetic clearance observation and explicit required/optional entry condition.
매개변수: `{"clear_ms": 2000, "wait_ms": 500, "deadline_ms": 2499, "required_entry": true}`.

| 출처 ID / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| S1: Pedestrian-entry waiting policy (SUPPLIED_SYNTHETIC_POLICY) | Enter only after 500 ms have elapsed since clearance. | $ e\Rightarrow u\ge\tau+500 $ |
| S2: Operator entry-time instruction (SUPPLIED_SYNTHETIC_OPERATOR_REQUIREMENT) | If entry occurs, its time must not exceed 2499 ms. | $ e\Rightarrow u\le 2499 $ |
### hold_departure: hold_departure-002

고정 맥락: Initial-origin and straight sampled-path modeling assumptions.
매개변수: `{"hold_ms": 500, "departure_sample_ms": 500, "required_x_mm": 201}`.

| 출처 ID / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| S3: Position-hold policy (SUPPLIED_SYNTHETIC_POLICY) | Stay within 200 mm of the origin through 500 ms, including the endpoint. | $ \bigwedge_{t_i\le 500}(x_i^2+y_i^2\le 200^2) $ |
| S4: Operator zone-clearance instruction (SUPPLIED_SYNTHETIC_OPERATOR_REQUIREMENT) | At the 500 ms sample, reach x of at least 201 mm. | $ x_{500}\ge 201 $ |
### speed_progress: speed_progress-002

고정 맥락: Nonnegative constant-speed modeling assumption over a specified duration.
매개변수: `{"cap_mm_s": 500, "horizon_s": 1, "minimum_mm": 501}`.

| 출처 ID / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| S5: Speed-limit policy (SUPPLIED_SYNTHETIC_POLICY) | Speed must not exceed 500 mm/s. | $ v\le 500 $ |
| S6: Operator minimum-progress instruction (SUPPLIED_SYNTHETIC_OPERATOR_REQUIREMENT) | Travel at least 501 mm within 1 s. | $ x\ge 501 $ |
### three_way_timing: three_way_timing-000

고정 맥락: Supplied synthetic stop-time anchor and nonnegative event-time assumptions.
매개변수: `{"wait_ms": 500, "delay_ms": 100, "deadline_ms": 599}`.

| 출처 ID / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| S7: Stop-release waiting policy (SUPPLIED_SYNTHETIC_POLICY) | Release no earlier than 500 ms after stopping. | $ r\ge s+500 $ |
| S8: Minimum release-to-entry transition latency (SUPPLIED_SYNTHETIC_MODELING_ASSUMPTION) | Assume entry takes at least 100 ms after release. | $ u\ge r+100 $ |
| S9: Operator final entry-time instruction (SUPPLIED_SYNTHETIC_OPERATOR_REQUIREMENT) | Enter no later than 599 ms after stopping. | $ u\le s+599 $ |

## 검사 결과

전체 636개 질의, UNKNOWN 0, 독립 판정 불일치 0.
SAT 해 601개를 독립 수치 계산으로 확인했고 잘못된 해는 0개다.
전체 모순 35개 모두 고정 맥락에 대한 부분집합 최소 모순 그룹을 확인했고, 그중 12개는 모든 두 조건 조합이 SAT다. 경계 수정 대조 35개는 SAT다.

## 해석과 범위

진입 의무가 없는 대조군에서는 두 진입 제한을 기다림으로 만족할 수 있다. 따라서 안전 제한과 진행 의무를 구분하고 맥락에 명시해야 한다. UNSAT는 지정된 맥락에서 요구사항들을 함께 만족할 수 없다는 뜻이며 어느 출처가 틀렸는지는 결정하지 않는다. 최소 모순 그룹은 고정 맥락에 대한 제약 그룹 단위이며, 최소 크기의 유일한 원인이나 현실 사고의 원인이라는 뜻이 아니다. 속도 과제는 일정 속도 가정이고 위치 유지는 표본 좌표 검사이며 연속시간 차량 안전을 보장하지 않는다. 여러 법규의 자동 추출, 법적 예외 보존, CNL의 조합 의미, 학습 행동 개선은 평가하지 않는다.

재현: `runtime/alpamayo/ar1_venv/bin/python projects/04-guardsynth-coc/experiments/paper1_cnl_learning/constraint_composition.py --run-id <unused-run-id>`
