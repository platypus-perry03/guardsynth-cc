# 위치 유지 과제 추가 학습 및 재평가

기존 temporal 어댑터 9개를 각각 960개 위치 유지 사례로 3 epoch 추가 학습했다. 각 fit은 180 optimizer update이며 마지막 epoch를 고정 사용했다. 모델은 A–D 후보를 선택한다. XY 궤적 생성·실차 제어·알파마요 비교 실험은 아니다.

P0 학습 입력은 원래 CoC, P1은 CoC+자연어 규칙, P2는 CoC+새 제한적 위치 유지 EBLC에서 생성한 CNL이다. 평가에서는 모든 조건에 동일 P2 CNL을 제공한다. 검증 여부와 문구 효과를 독립적으로 분리한 실험은 아니다.

학습 120 geometry profile/960행, validation 16 profile/128행, 테스트 32 profile/256행이다. 같은 profile의 label rotation·duration·encoding은 같은 split에 둔다. validation은 보관만 하고 checkpoint 선택에 사용하지 않았다. 추가 사람 라벨링 없이 합성 궤적·규칙으로 기준 정답을 자동 계산했다. 각 profile은 두 label rotation × 두 대기 시간 × 두 표현 방식의 8개 관련 사례를 낳으므로 행은 독립 도로 장면이 아니다.

별도 integer oracle은 모든 검사 시점의 x²+y²≤200²를 평가하며, 5376개 후보에서 SMT 판정과 일치했다. 0.5/2.0초 끝점을 포함하며 중간에 밖으로 나갔다가 돌아오는 경우도 위반이다. 0.01m 측정 허용오차는 보조 지표로 별도 기록한다.

|집합|표현|조건|대기|정답/192|위반/192|0.01m 허용 후 위반|최대 초과(m)|
|---|---|---|---|---:|---:|---:|---:|
|before_test|interval_maxima|P0|0.5s|92|29|29|0.182200|
|before_test|interval_maxima|P0|2.0s|121|64|64|0.197800|
|before_test|interval_maxima|P1|0.5s|108|13|13|0.091400|
|before_test|interval_maxima|P1|2.0s|165|23|23|0.197800|
|before_test|interval_maxima|P2|0.5s|100|7|7|0.138000|
|before_test|interval_maxima|P2|2.0s|157|20|20|0.197800|
|before_test|xy_waypoints|P0|0.5s|92|56|56|0.197800|
|before_test|xy_waypoints|P0|2.0s|63|121|121|0.198600|
|before_test|xy_waypoints|P1|0.5s|99|49|49|0.197800|
|before_test|xy_waypoints|P1|2.0s|65|126|126|0.198600|
|before_test|xy_waypoints|P2|0.5s|96|53|53|0.182800|
|before_test|xy_waypoints|P2|2.0s|76|115|115|0.197800|
|after_test|interval_maxima|P0|0.5s|129|0|0|0.000000|
|after_test|interval_maxima|P0|2.0s|167|22|22|0.197800|
|after_test|interval_maxima|P1|0.5s|172|1|1|0.025000|
|after_test|interval_maxima|P1|2.0s|189|1|1|0.042800|
|after_test|interval_maxima|P2|0.5s|182|1|1|0.091400|
|after_test|interval_maxima|P2|2.0s|189|0|0|0.000000|
|after_test|xy_waypoints|P0|0.5s|119|1|1|0.041000|
|after_test|xy_waypoints|P0|2.0s|169|23|23|0.197800|
|after_test|xy_waypoints|P1|0.5s|156|5|5|0.056400|
|after_test|xy_waypoints|P1|2.0s|175|16|16|0.197800|
|after_test|xy_waypoints|P2|0.5s|174|3|3|0.032800|
|after_test|xy_waypoints|P2|2.0s|188|4|4|0.090000|
|after_regression|interval_maxima|P0|0.5s|154|0|0|0.000000|
|after_regression|interval_maxima|P0|2.0s|136|53|18|0.050000|
|after_regression|interval_maxima|P1|0.5s|174|0|0|0.000000|
|after_regression|interval_maxima|P1|2.0s|172|16|1|0.050000|
|after_regression|interval_maxima|P2|0.5s|186|0|0|0.000000|
|after_regression|interval_maxima|P2|2.0s|189|1|0|0.001000|
|after_regression|xy_waypoints|P0|0.5s|157|5|5|0.015411|
|after_regression|xy_waypoints|P0|2.0s|80|106|53|0.050000|
|after_regression|xy_waypoints|P1|0.5s|153|17|17|0.015411|
|after_regression|xy_waypoints|P1|2.0s|113|79|41|0.050000|
|after_regression|xy_waypoints|P2|0.5s|144|40|39|0.015411|
|after_regression|xy_waypoints|P2|2.0s|114|77|50|0.050000|

before_test/after_test는 같은 새 테스트셋·같은 입력에서 학습 전후를 비교한다. after_regression은 이미 관찰한 이전 256개 사례의 회귀 검사이며 새로운 독립 테스트로 주장하지 않는다. 학습으로 관측 위반이 감소하더라도 모든 상황에서 준수한다는 보장은 아니다. 숫자 입력을 이용하는 합성 과제이며 실영상 일반화·연속 시간 안전성은 검사하지 않았다.
