# 기존 XY 위치 유지 진단의 P1·P2 위반 분석

결론: 명세에 빠진 조건 때문에 허용된 후보가 아니라, 이미 금지된 후보를 모델이 선택한 오류다. 거리 계산과 모든 시점 확인을 모델에 맡기는 현재 방식만으로는 준수 문제가 해결되지 않았다. 원인은 내부 추론을 관찰하지 않았으므로 확정할 수 없다.

기존 16개 수치 궤적 구성 × 4개 라벨 회전 × 두 대기 시간에서 P1·P2 세 시드의 추가 학습 전후 XY 예측 1,536개를 재채점했다. 각 XY 응답에는 동일 사례의 최대 거리 제공 응답이 짝지어져 있다. 추가 추론·훈련·사람 레이블링을 하지 않았다. 이들은 서로 관련된 합성 사례이고 기존에 검토한 진단셋이다.

모든 평가 모델은 같은 규칙을 받았다: 모든 제시 시점 t≤대기 시간에서 초기 위치와의 방사형 거리가 0.200m 이하여야 하며 끝점을 포함한다. 종료 후 움직임은 허용된다. 정수 검사식은 x²+y²≤40,000(mm²)이다. 제공된 시점 사이의 연속 궤적은 검사하지 않는다.

## 1. 위반 유형과 학습 전후

|모델|대기|위반 전→후 /192|조기 대각선 이탈 전→후|0.5초에는 허용, 2초에는 금지인 후보 전→후|
|---|---|---:|---:|---:|
|P1|0.5초|6→17|6→17|0→0|
|P1|2초|91→79|7→8|84→71|
|P2|0.5초|8→40|8→40|0→0|
|P2|2초|75→77|9→28|66→49|

조기 대각선 후보는 0.25초 또는 0.5초에 한도를 넘고 이후 복귀한다. 두 번째 후보는 0.5초까지 허용되지만 1초에 x=0.201/0.210/0.211/0.250m가 되어 2초 조건을 위반한다. 둘 모두 2초에는 원점으로 돌아온다. 아래 성질은 겹칠 수 있으며 모델이 실제로 사용한 판단 방식이라는 뜻은 아니다.

## 2. 추가 학습 후 위반의 세부 성질

|모델|대기|위반|초과 ≤10mm / >10mm|X·Y 각각만 검사하면 통과|끝점만 검사하면 통과|전체 후보 중 최고 점수|
|---|---|---:|---:|---:|---:|---:|
|P1|0.5초|17|0 / 17|17|9|15|
|P1|2초|79|38 / 41|8|79|55|
|P2|0.5초|40|1 / 39|40|22|35|
|P2|2초|77|27 / 50|28|77|55|

0.5초 위반은 전부 X·Y 각각은 0.2m 이내이지만 방사형 거리가 한도를 넘는 대각선 후보다. 2초 위반은 전부 끝점에 복귀한 후보이므로 끝점만 확인하면 놓친다. 10mm보다 큰 위반도 많아 1mm 경계 오차만으로 설명할 수 없다. 점수가 높은 위반 후보 선택이 많지만 점수 때문에 규칙을 무시했다고 인과적으로 입증한 것은 아니다.

## 3. 같은 사례에서 최대 거리 계산값을 제공한 결과

|모델|대기|XY 위반|짝지은 최대 거리 응답이 비위반|짝지은 최대 거리 응답이 정답|
|---|---|---:|---:|---:|
|P1|0.5초|17|17|17|
|P1|2초|79|65|61|
|P2|0.5초|40|40|39|
|P2|2초|77|77|75|

모델·시드·이미지·규칙·좌표가 나타내는 궤적·후보 라벨·점수는 같다. 달라지는 것은 후보의 수치 표현이다: XY 좌표 목록 대신 계산된 구간 최대 거리를 제공한다. 이는 계산/시간 집계 부담 또는 표현 민감성의 관여를 뒷받침하지만, 내부 오류가 산술인지 시점 누락인지 분리하지는 못한다. 최대 거리를 제공하는 것은 입력 정보의 가공이며 제약 문장만 추가하는 조치가 아니다.

## 4. 실제 위반 사례

### diagonal_excursion_return: P2, seed 42

사례 `profile-04-rotation-0-500-xy_waypoints`: 선택 A, 기준 정답 C; 최대 거리 0.214009m, 초과 14.009346mm; SMT UNSAT.

Requirement CoC: Remain at the current position until the required hold period has ended, then proceed when permitted.

Constraint: Hold the ego vehicle's initial position for at least 0.5 s. At every listed waypoint with t <= 0.5 s, including the endpoint, the radial XY distance from the initial position must be at most 0.200 m. Movement after that period is permitted.

|시각(s)|선택 후보 X(m)|선택 후보 Y(m)|방사형 거리(m)|대기 구간|
|---:|---:|---:|---:|---|
|0|0.000|0.000|0.000000|검사 대상|
|0.25|0.130|0.170|0.214009|검사 대상|
|0.5|0.000|0.000|0.000000|검사 대상|
|1|0.000|0.000|0.000000|종료 후 이동 허용|
|1.5|0.000|0.000|0.000000|종료 후 이동 허용|
|2|0.000|0.000|0.000000|종료 후 이동 허용|
|2.1|1.100|0.000|1.100000|종료 후 이동 허용|

### inclusive_endpoint_diagonal: P1, seed 42

사례 `profile-10-rotation-2-500-xy_waypoints`: 선택 C, 기준 정답 A; 최대 거리 0.215411m, 초과 15.411235mm; SMT UNSAT.

Requirement CoC: Remain at the current position until the required hold period has ended, then proceed when permitted.

Constraint: Hold the ego vehicle's initial position for at least 0.5 s. At every listed waypoint with t <= 0.5 s, including the endpoint, the radial XY distance from the initial position must be at most 0.200 m. Movement after that period is permitted.

|시각(s)|선택 후보 X(m)|선택 후보 Y(m)|방사형 거리(m)|대기 구간|
|---:|---:|---:|---:|---|
|0|0.000|0.000|0.000000|검사 대상|
|0.25|0.000|0.000|0.000000|검사 대상|
|0.5|0.131|0.171|0.215411|검사 대상|
|1|0.000|0.000|0.000000|종료 후 이동 허용|
|1.5|0.000|0.000|0.000000|종료 후 이동 허용|
|2|0.000|0.000|0.000000|종료 후 이동 허용|
|2.1|1.100|0.000|1.100000|종료 후 이동 허용|

### late_axis_1mm: P2, seed 42

사례 `profile-03-rotation-3-2000-xy_waypoints`: 선택 A, 기준 정답 B; 최대 거리 0.201000m, 초과 1.000000mm; SMT UNSAT.

Requirement CoC: Remain at the current position until the required hold period has ended, then proceed when permitted.

Constraint: Hold the ego vehicle's initial position for at least 2.0 s. At every listed waypoint with t <= 2.0 s, including the endpoint, the radial XY distance from the initial position must be at most 0.200 m. Movement after that period is permitted.

|시각(s)|선택 후보 X(m)|선택 후보 Y(m)|방사형 거리(m)|대기 구간|
|---:|---:|---:|---:|---|
|0|0.000|0.000|0.000000|검사 대상|
|0.25|0.050|0.000|0.050000|검사 대상|
|0.5|0.200|0.000|0.200000|검사 대상|
|1|0.201|0.000|0.201000|검사 대상|
|1.5|0.100|0.000|0.100000|검사 대상|
|2|0.000|0.000|0.000000|검사 대상|
|2.1|1.000|0.000|1.000000|종료 후 이동 허용|

### late_axis_50mm: P1, seed 42

사례 `profile-12-rotation-2-2000-xy_waypoints`: 선택 D, 기준 정답 A; 최대 거리 0.250000m, 초과 50.000000mm; SMT UNSAT.

Requirement CoC: Remain at the current position until the required hold period has ended, then proceed when permitted.

Constraint: Hold the ego vehicle's initial position for at least 2.0 s. At every listed waypoint with t <= 2.0 s, including the endpoint, the radial XY distance from the initial position must be at most 0.200 m. Movement after that period is permitted.

|시각(s)|선택 후보 X(m)|선택 후보 Y(m)|방사형 거리(m)|대기 구간|
|---:|---:|---:|---:|---|
|0|0.000|0.000|0.000000|검사 대상|
|0.25|0.050|0.000|0.050000|검사 대상|
|0.5|0.200|0.000|0.200000|검사 대상|
|1|0.250|0.000|0.250000|검사 대상|
|1.5|0.100|0.000|0.100000|검사 대상|
|2|0.000|0.000|0.000000|검사 대상|
|2.1|1.000|0.000|1.000000|종료 후 이동 허용|

## 5. 제약사항만으로 해결할 수 있는가?

- 조건 추가 필요성: 관측된 213개 학습 후 위반 모두 현재 규칙과 SMT에서 이미 거부된다. 새 금지 조건이 빠져서 생긴 사례는 이번 자료에서 확인하지 못했다.
- 문장 보강: x²+y²와 모든 시점의 최댓값 계산 절차를 명시하는 방법은 시험할 수 있지만, 이번 분석에서는 새 문구를 실행하지 않았으므로 해결된다고 주장할 수 없다.
- 수치 전처리: 기존 최대 거리 제공 짝 비교에서 P1 XY 위반 96건 중 82건, P2 117건 중 117건이 비위반 선택으로 바뀌었다. 규칙만으로 충분하다는 증거가 아니라 입력 표현의 영향을 보여준다.
- 강제 검사: 저장된 선택에 현재 SMT를 적용하면 P1의 96건과 P2의 117건을 전부 거부한다. 이는 오프라인 조건부 거부 계산이다. 거부 후 재선택·기권을 처리하는 실행 장치를 평가한 것은 아니며 신경망 자체의 성능 향상도 아니다.
- 학습 범위: 새 학습 데이터의 금지 후보는 최소 20mm 초과하지만 기존 진단은 1mm부터 시작한다. 궤적 패턴·점수·도식도 달라 단일 원인은 분리하지 못했다. 이미 검토한 진단셋을 다시 학습시키고 동일셋으로 평가하면 독립 일반화 증거가 되지 않는다.

512개 고유 사례-후보 조합에서 SMT와 독립 정수/거리 계산이 모두 일치했고, 1,536개 XY 예측을 원래 점수와 대조했다. 모든 선택에는 실제 SMT 판정을 연결했다. 현재 확인 범위는 정확히 제공된 유한 시점·후보이며 실차 제어나 연속 시간 안전성 보장이 아니다.

[모든 위반과 전체 후보](violation_cases.jsonl) · [대표 사례](representative_cases.json) · [집계 CSV](error_summary.csv) · [전체 예측 분석](observations.jsonl)
