# VLM 크기와 semantic loss 비교 결과

E1은 추가 학습 없는 Qwen3-VL 2B·8B 평가, E2는 규칙 유무 × semantic loss 유무의 네 조건을 같은 2B 초기 모델에서 새로 학습한 비교다.
E2: 과제당 960행, 3 epochs, 180 updates, 시드 42·17·123, 총 24회 학습. 테스트는 temporal 240행, 위치 유지 256행(최대 거리/XY 각 128행)이다.

## E2: 네 학습 조건

평균 ± 시드 간 표준편차(%p). 각 점수는 두 유지/대기 시간을 함께 포함한다. 위반율은 전체 예측이 분모이며 답 추출 실패율을 별도로 표시한다. 쌍 정확도는 같은 장면·후보에 서로 다른 규칙을 적용한 두 문항을 모두 맞힌 비율이다.

| 과제·표현 | 조건 | 정확도 | 위반율 | 답 추출 실패 | 쌍 정확도 |
|---|---|---:|---:|---:|---:|
| Temporal entry | CE / no rule | 49.86 ± 0.24 | 19.58 ± 6.14 | 0.00% | 0.00% |
| Temporal entry | CE + semantic / no rule | 50.00 ± 0.00 | 0.00 ± 0.00 | 0.00% | 0.00% |
| Temporal entry | CE / CNL | 98.47 ± 1.20 | 1.11 ± 1.58 | 0.00% | 96.94% |
| Temporal entry | CE + semantic / CNL | 97.64 ± 2.14 | 0.83 ± 1.44 | 0.00% | 95.28% |
| Position hold: maxima | CE / no rule | 75.00 ± 0.00 | 10.94 ± 1.35 | 0.00% | 50.00% |
| Position hold: maxima | CE + semantic / no rule | 74.48 ± 0.90 | 1.56 ± 1.56 | 0.00% | 49.48% |
| Position hold: maxima | CE / CNL | 96.09 ± 1.35 | 0.00 ± 0.00 | 0.00% | 92.71% |
| Position hold: maxima | CE + semantic / CNL | 96.09 ± 2.34 | 0.00 ± 0.00 | 0.00% | 92.71% |
| Position hold: XY | CE / no rule | 72.66 ± 1.35 | 10.94 ± 2.71 | 0.00% | 48.44% |
| Position hold: XY | CE + semantic / no rule | 74.74 ± 0.45 | 0.52 ± 0.90 | 0.00% | 50.00% |
| Position hold: XY | CE / CNL | 93.49 ± 1.19 | 1.56 ± 0.78 | 0.00% | 86.98% |
| Position hold: XY | CE + semantic / CNL | 92.71 ± 3.61 | 2.08 ± 2.96 | 0.00% | 85.42% |

규칙을 제공한 CE 조건과 CE + semantic 조건의 직접 비교:

- Temporal entry: 정확도 98.47% → 97.64%, 위반율 1.11% → 0.83%.
- Position hold: maxima: 정확도 96.09% → 96.09%, 위반율 0.00% → 0.00%.
- Position hold: XY: 정확도 93.49% → 92.71%, 위반율 1.56% → 2.08%.

## E2: 동일 입력에서 semantic loss의 추가 효과

각 시드에서 semantic 조건 − CE 조건을 구한 뒤 평균했다. 정확도 증가는 양수, 위반율 감소는 음수다. 학습 입력의 규칙 유무를 고정한 비교다.

| 과제·표현 | 규칙 | 정확도 차이(%p) | 위반율 차이(%p) |
|---|---|---:|---:|
| temporal / candidate_scalars | no_rule | +0.14 | -19.58 |
| temporal / candidate_scalars | rule | -0.83 | -0.28 |
| position_hold / interval_maxima | no_rule | -0.52 | -9.38 |
| position_hold / interval_maxima | rule | +0.00 | +0.00 |
| position_hold / xy_waypoints | no_rule | +2.08 | -10.42 |
| position_hold / xy_waypoints | rule | -0.78 | +0.52 |

## E2: 2초 위치 유지

| 표현 | 조건 | 정확도 | 위반율 | 예측 수 |
|---|---|---:|---:|---:|
| interval_maxima | ce_no_rule | 78.12% | 21.88% | 192 |
| xy_waypoints | ce_no_rule | 81.25% | 18.75% | 192 |
| interval_maxima | semantic_no_rule | 96.35% | 3.12% | 192 |
| xy_waypoints | semantic_no_rule | 99.48% | 0.52% | 192 |
| interval_maxima | ce_rule | 99.48% | 0.00% | 192 |
| xy_waypoints | ce_rule | 99.48% | 0.52% | 192 |
| interval_maxima | semantic_rule | 99.48% | 0.00% | 192 |
| xy_waypoints | semantic_rule | 98.44% | 1.04% | 192 |

## E2: 모든 모델에 평가 때 같은 CNL 제공

위 네 조건의 주 평가와 분리한 보조 검사다. 규칙 없이 학습한 어댑터에는 평가 입력만 바꾸며 재학습하지 않았다. CNL과 함께 학습한 두 조건은 주 평가의 같은 예측을 재사용한다. 따라서 이 표에서는 평가 정보가 같고 학습 입력과 손실만 다르다.

| 과제·표현 | 학습 조건 | 정확도 | 위반율 |
|---|---|---:|---:|
| Temporal entry | CE / no rule | 50.14% | 17.92% |
| Temporal entry | CE + semantic / no rule | 50.00% | 0.00% |
| Temporal entry | CE / CNL | 98.47% | 1.11% |
| Temporal entry | CE + semantic / CNL | 97.64% | 0.83% |
| Position hold: maxima | CE / no rule | 78.39% | 6.51% |
| Position hold: maxima | CE + semantic / no rule | 75.52% | 0.26% |
| Position hold: maxima | CE / CNL | 96.09% | 0.00% |
| Position hold: maxima | CE + semantic / CNL | 96.09% | 0.00% |
| Position hold: XY | CE / no rule | 75.52% | 6.25% |
| Position hold: XY | CE + semantic / no rule | 74.74% | 0.52% |
| Position hold: XY | CE / CNL | 93.49% | 1.56% |
| Position hold: XY | CE + semantic / CNL | 92.71% | 2.08% |

## E1: 학습 없는 모델의 출력 한도별 결과

12토큰은 사전에 고정한 주 평가다. 설명 출력이 잘리는 현상을 확인한 뒤 512토큰과 최종 답 추출을 추가한 결과는 사후 보조 평가다. 입력·이미지는 동일하다. 두 결과를 함께 보고하며 좋은 값으로 대체하지 않는다. 주 평가 배치는 두 모델 모두 4이며, 보조 평가는 8B 배치 2, 2B 배치 8이다. 전처리·생성 병목으로 2B 배치를 변경한 뒤 전체 입력을 다시 실행했으며, 앞선 배치 2의 부분 결과는 집계하지 않았다. 모델 간 실행 속도는 비교하지 않는다.

| 모델 | 출력 한도 | 과제·표현 | 정확도 | 위반율 | 답 추출 실패 | 한도 도달/전체 |
|---|---:|---|---:|---:|---:|---:|
| 2b | 12 | temporal / candidate_scalars | 0.00% | 0.00% | 100.00% | 240/240 |
| 2b | 12 | max_speed / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 12 | min_clearance / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 12 | min_entry_delay / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 12 | cruise_stop / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 12 | lane_change / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 12 | position_hold / interval_maxima | 0.00% | 0.00% | 100.00% | 128/128 |
| 2b | 12 | position_hold / xy_waypoints | 0.00% | 0.00% | 100.00% | 128/128 |
| 2b | 512 | temporal / candidate_scalars | 10.83% | 11.25% | 65.42% | 240/240 |
| 2b | 512 | max_speed / candidate_scalars | 50.00% | 50.00% | 0.00% | 0/48 |
| 2b | 512 | min_clearance / candidate_scalars | 50.00% | 50.00% | 0.00% | 0/48 |
| 2b | 512 | min_entry_delay / candidate_scalars | 54.17% | 14.58% | 31.25% | 15/48 |
| 2b | 512 | cruise_stop / candidate_scalars | 0.00% | 0.00% | 100.00% | 48/48 |
| 2b | 512 | lane_change / candidate_scalars | 37.50% | 8.33% | 54.17% | 26/48 |
| 2b | 512 | position_hold / interval_maxima | 14.84% | 0.00% | 79.69% | 112/128 |
| 2b | 512 | position_hold / xy_waypoints | 7.03% | 7.03% | 75.78% | 128/128 |
| 8b | 12 | temporal / candidate_scalars | 27.08% | 68.75% | 0.00% | 0/240 |
| 8b | 12 | max_speed / candidate_scalars | 60.42% | 39.58% | 0.00% | 0/48 |
| 8b | 12 | min_clearance / candidate_scalars | 54.17% | 45.83% | 0.00% | 0/48 |
| 8b | 12 | min_entry_delay / candidate_scalars | 50.00% | 50.00% | 0.00% | 0/48 |
| 8b | 12 | cruise_stop / candidate_scalars | 50.00% | 25.00% | 0.00% | 0/48 |
| 8b | 12 | lane_change / candidate_scalars | 75.00% | 0.00% | 0.00% | 0/48 |
| 8b | 12 | position_hold / interval_maxima | 70.31% | 7.03% | 0.00% | 0/128 |
| 8b | 12 | position_hold / xy_waypoints | 35.94% | 33.59% | 20.31% | 26/128 |
| 8b | 512 | temporal / candidate_scalars | 27.50% | 66.67% | 0.00% | 0/240 |
| 8b | 512 | max_speed / candidate_scalars | 60.42% | 39.58% | 0.00% | 0/48 |
| 8b | 512 | min_clearance / candidate_scalars | 54.17% | 45.83% | 0.00% | 0/48 |
| 8b | 512 | min_entry_delay / candidate_scalars | 50.00% | 50.00% | 0.00% | 0/48 |
| 8b | 512 | cruise_stop / candidate_scalars | 50.00% | 25.00% | 0.00% | 0/48 |
| 8b | 512 | lane_change / candidate_scalars | 75.00% | 0.00% | 0.00% | 0/48 |
| 8b | 512 | position_hold / interval_maxima | 70.31% | 7.03% | 0.00% | 0/128 |
| 8b | 512 | position_hold / xy_waypoints | 36.72% | 34.38% | 17.19% | 29/128 |

답을 추출할 수 없는 출력은 허용 행동으로 처리하지 않는다. 특히 답 추출 실패율 100%와 관측 위반율 0%의 조합은 준수 성공이 아니다. 한도에 도달한 텍스트에서 추출된 레이블도 완결된 최종 응답과 구분해야 한다. 긴 설명으로 출력 한도에 걸린 점수는 규칙 추론 능력만의 측정이 아니다. 512토큰 결과의 기존 엄격 파서 점수도 RESULT.json에 보존했다.

## 해석과 범위

규칙 없이 평가하는 조건에서 동일 입력의 정답 식별 상한은 temporal 50%, 위치 유지 75%다. 손실에 허용 후보를 알려주더라도, 평가 입력에 없는 사례별 규칙을 복원할 수는 없다. 낮은 위반율과 높은 정답률은 별개이므로 쌍 정확도도 함께 본다. 2초 사례에서 엄격한 유지 후보만 고르면 잘 맞힐 수 있어도, 0.5초 사례와의 적절한 구별은 별도로 확인해야 한다.

두 과제 모두 사전학습 모델에서 fresh LoRA를 시작했다. 과거 temporal 어댑터를 이어 학습한 위치 유지 결과와 초기화 이력이 달라 숫자를 직접적인 향상/저하로 해석하지 않는다.

Semantic loss는 허용 레이블의 A–D 조건부 확률 합에 적용한 범주형 방식이다. 가중치 1을 실행 전에 고정했으며 이 결과로 다른 가중치를 탐색하지 않았다. 추론 때 후보를 제거하거나 SMT로 출력을 교정하지 않았다. 조건부 손실은 임의 출력이나 실제 차량의 안전을 보장하지 않는다.

본 결과는 고정된 합성 후보 선택 입력의 평가다. Alpamayo·nuScenes 사전 진단의 궤적 생성 실험과는 별개다. 새로운 실제 도로 장면이나 궤적 생성 모델의 개선을 입증하지 않으며, 큰 VLM의 성공/실패를 학습의 보편적 필요성으로 일반화하지 않는다.

E1은 과제 형식에 대한 추가 학습이 없는 zero-shot 비교이므로, 학습 모델과의 차이에는 과제 적응 효과도 포함된다. 동일 입력과 학습 예산에서 손실의 추가 효과를 분리한 비교는 E2다.

실행 세션 중단으로 모델 저장 전 종료된 여섯 학습은 같은 초기 모델과 시드에서 처음부터 재실행했다. 중단된 시도의 로그와 진행 기록은 보존했으며, 완료된 24개 학습만 집계했다. 초기화 일치와 각 학습의 180회 업데이트를 다시 확인했다. 학습을 마치고 저장된 temporal 어댑터 하나는 재학습 없이 평가를 이어갔으며, 2B 보조 추론도 완료된 배치 다음부터 같은 배치 크기로 재개했다.

Semantic loss 원문: https://proceedings.mlr.press/v80/xu18h.html
8B 모델 카드: https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct

[E2 조건별 입력 그래프](semantic_loss_comparison.pdf) · [E2 동일 CNL 평가 그래프](common_rule_comparison.pdf) · [E1 출력 한도 비교](pretrained_vlm_comparison.pdf)
