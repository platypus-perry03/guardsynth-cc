# 추가 정적·기동 제약 학습 결과

24 fits, 3 seeds, 2,160 optimizer updates. 모든 조건·실패·일반화 결과를 보존한다. 스모크 실행은 별도다.
P0: CoC만. P1: 기존 자연어 제약 추가. P2: EBLC→Core 검증→CNL 제약 추가. SHUFFLED_GUARD: P2 학습 문장만 같은 유형 안에서 교란.
P1/P2는 학습과 평가 모두 제약을 받는다. 검증 자체의 인과적 학습 이득이나 실제 도로 운전을 입증하는 실험이 아니다.
위반·완료·보수성·coverage 분모는 해당 층의 모든 행이다. 부적합 출력은 위반이나 deadlock으로 바꾸지 않고 coverage에 반영한다.
계약쌍 정확도는 같은 후보의 permissive/restrictive 둘 다 맞힌 비율이다. 정확도는 허용 후보 중 최대 진행 후보와의 일치다.

## static

| 조건/분포 | 정확도 | 위반 | 제약 준수 완료 | 불필요 보수성 | deadlock | coverage | 계약쌍 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 / test | 50.00% | 24.31% | 75.69% | 25.69% | 0.00% | 100.00% | 0.00% |
| P1 / test | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% | 100.00% | 100.00% |
| P2 / test | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% | 100.00% | 100.00% |
| SHUFFLED_GUARD / test | 50.69% | 23.84% | 76.16% | 25.46% | 0.00% | 100.00% | 3.70% |
| P0 / paraphrase | 50.00% | 24.31% | 75.69% | 25.69% | 0.00% | 100.00% | 0.00% |
| P1 / paraphrase | 93.29% | 0.00% | 100.00% | 6.71% | 0.00% | 100.00% | 86.57% |
| P2 / paraphrase | 80.32% | 7.87% | 92.13% | 11.81% | 0.00% | 100.00% | 60.65% |
| SHUFFLED_GUARD / paraphrase | 50.23% | 24.77% | 75.23% | 25.00% | 0.00% | 100.00% | 0.46% |
| P0 / unseen | 50.00% | 22.92% | 77.08% | 27.08% | 0.00% | 100.00% | 0.00% |
| P1 / unseen | 99.54% | 0.00% | 100.00% | 0.46% | 0.00% | 100.00% | 99.07% |
| P2 / unseen | 97.22% | 0.23% | 99.77% | 2.55% | 0.00% | 100.00% | 94.44% |
| SHUFFLED_GUARD / unseen | 49.31% | 25.00% | 75.00% | 25.69% | 0.00% | 100.00% | 3.70% |

하위 유형·각 시드·모든 지표: metrics.csv. 대응 차이와 탐색적 bootstrap 구간: RESULT.json.

데이터 목록:

| 분포 | 행 | scene ID | 실제 고유 그림 | 학습 그림 중복 |
|---|---:|---:|---:|---:|
| train | 576 | 96 | 18 | 18 |
| test | 144 | 24 | 13 | 13 |
| paraphrase | 144 | 24 | 13 | 13 |
| unseen | 144 | 24 | 8 | 0 |

- Supplied synthetic candidate summaries, not real-road extraction or closed-loop control.
- Candidate scalars are in text; images are schematic and may repeat across splits.
- P0 lacks the variable contract and has contradictory paired targets.
- P1/P2 receive constraints during training and evaluation; not train-only benefit.
- Finite candidate stop/gap checks do not prove continuous abort/retry dynamics.
- Exact thresholds retain milli-unit precision; legacy one-decimal wording is corrected in all guarded arms.
- Paraphrase reuses test scenes; hard combines boundary, wording and units, not factorial.
- Three optimization seeds and synthetic parameter templates do not establish road generalization.

## maneuver

| 조건/분포 | 정확도 | 위반 | 제약 준수 완료 | 불필요 보수성 | deadlock | coverage | 계약쌍 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 / test | 50.00% | 30.90% | 69.10% | 19.10% | 0.00% | 100.00% | 0.00% |
| P1 / test | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% | 100.00% | 100.00% |
| P2 / test | 98.96% | 0.00% | 100.00% | 1.04% | 0.00% | 100.00% | 97.92% |
| SHUFFLED_GUARD / test | 49.65% | 30.56% | 69.44% | 19.79% | 0.00% | 100.00% | 2.08% |
| P0 / paraphrase | 50.00% | 30.90% | 69.10% | 19.10% | 0.00% | 100.00% | 0.00% |
| P1 / paraphrase | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% | 100.00% | 100.00% |
| P2 / paraphrase | 97.92% | 2.08% | 97.92% | 0.00% | 0.00% | 100.00% | 95.83% |
| SHUFFLED_GUARD / paraphrase | 52.43% | 26.74% | 73.26% | 20.83% | 0.00% | 100.00% | 5.56% |
| P0 / unseen | 50.00% | 30.90% | 69.10% | 19.10% | 0.00% | 100.00% | 0.00% |
| P1 / unseen | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% | 100.00% | 100.00% |
| P2 / unseen | 98.96% | 0.00% | 100.00% | 1.04% | 0.00% | 100.00% | 97.92% |
| SHUFFLED_GUARD / unseen | 49.65% | 30.90% | 69.10% | 19.44% | 0.00% | 100.00% | 2.78% |
| P0 / hard | 50.00% | 30.21% | 69.79% | 19.79% | 0.00% | 100.00% | 0.00% |
| P1 / hard | 94.10% | 0.69% | 99.31% | 5.21% | 0.00% | 100.00% | 88.19% |
| P2 / hard | 91.32% | 1.04% | 98.96% | 7.64% | 0.00% | 100.00% | 82.64% |
| SHUFFLED_GUARD / hard | 51.04% | 32.29% | 67.71% | 16.67% | 0.00% | 100.00% | 2.08% |

하위 유형·각 시드·모든 지표: metrics.csv. 대응 차이와 탐색적 bootstrap 구간: RESULT.json.

데이터 목록:

| 분포 | 행 | scene ID | 실제 고유 그림 | 학습 그림 중복 |
|---|---:|---:|---:|---:|
| train | 384 | 192 | 2 | 2 |
| test | 96 | 48 | 2 | 2 |
| paraphrase | 96 | 48 | 2 | 2 |
| unseen | 96 | 48 | 2 | 2 |
| hard | 96 | 48 | 2 | 2 |

- Supplied synthetic candidate summaries, not real-road extraction or closed-loop control.
- Candidate scalars are in text; images are schematic and may repeat across splits.
- P0 lacks the variable contract and has contradictory paired targets.
- P1/P2 receive constraints during training and evaluation; not train-only benefit.
- Finite candidate stop/gap checks do not prove continuous abort/retry dynamics.
- Exact thresholds retain milli-unit precision; legacy one-decimal wording is corrected in all guarded arms.
- Paraphrase reuses test scenes; hard combines boundary, wording and units, not factorial.
- Three optimization seeds and synthetic parameter templates do not establish road generalization.

## 원고 반영 제안

- 본문: 정적 3유형·정지·차선 변경의 P0/P1/P2 대응 비교. 이는 제약 정보 제공 효과와 표현 변경의 결과를 구별한다.
- 동일 문장 교란 대조를 함께 넣어 올바른 대상·제약 연결의 중요성을 평가한다.
- 재표현·미관측 수치·복합 hard 결과는 좋고 나쁨에 관계없이 강건성 표에 포함한다.
- 원본/빈/교환 영상 진단 2,160건은 별도 분포의 기존 모델 진단이며 이 신규 학습과 합산하지 않는다.
- 그림·scene ID 반복과 텍스트 후보 정보 때문에 새 물리 환경에 대한 영상 일반화로 주장하지 않는다.
- 본 보고서는 결과를 먼저 제시하며 원고는 아직 수정하지 않았다.

불확실성: 최적화 시드 3개와 숫자 설정 cluster를 대응 재표집한 2,000회 bootstrap. 장면 수나 프레임 수를 독립 표본처럼 취급하지 않았다.
아래 그림은 평균 막대와 각 시드 점을 모두 보인다.

![Accuracy](accuracy.svg)

![Violation](violation.svg)

![Compliant completion](completion.svg)
