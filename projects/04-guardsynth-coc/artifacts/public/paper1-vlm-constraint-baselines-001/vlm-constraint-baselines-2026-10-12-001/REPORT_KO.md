# VLM 크기 및 semantic loss 비교

상태: COMPLETE; E1 완료 모델 2/2; E2 완료 학습 24/24.

동일 입력을 사용하는 규칙 조건끼리 손실 효과를 비교한다. 무규칙 조건의 정보 한계와 낮은 위반율에 의한 보수적 선택을 분리한다.

| 실험 | 모델/조건 | 과제 | 표현 | 평가 입력 | 정확도 | 위반율 | 잘못된 출력 |
|---|---|---|---|---|---:|---:|---:|
| E2 | 2b / ce_no_rule | position_hold | interval_maxima | arm_input | 75.00% | 10.94% | 0.00% |
| E2 | 2b / ce_no_rule | position_hold | xy_waypoints | arm_input | 72.66% | 10.94% | 0.00% |
| E2 | 2b / ce_no_rule | position_hold | interval_maxima | common_rule | 78.39% | 6.51% | 0.00% |
| E2 | 2b / ce_no_rule | position_hold | xy_waypoints | common_rule | 75.52% | 6.25% | 0.00% |
| E2 | 2b / ce_rule | position_hold | interval_maxima | arm_input | 96.09% | 0.00% | 0.00% |
| E2 | 2b / ce_rule | position_hold | xy_waypoints | arm_input | 93.49% | 1.56% | 0.00% |
| E2 | 2b / semantic_no_rule | position_hold | interval_maxima | arm_input | 74.48% | 1.56% | 0.00% |
| E2 | 2b / semantic_no_rule | position_hold | xy_waypoints | arm_input | 74.74% | 0.52% | 0.00% |
| E2 | 2b / semantic_no_rule | position_hold | interval_maxima | common_rule | 75.52% | 0.26% | 0.00% |
| E2 | 2b / semantic_no_rule | position_hold | xy_waypoints | common_rule | 74.74% | 0.52% | 0.00% |
| E2 | 2b / semantic_rule | position_hold | interval_maxima | arm_input | 96.09% | 0.00% | 0.00% |
| E2 | 2b / semantic_rule | position_hold | xy_waypoints | arm_input | 92.71% | 2.08% | 0.00% |
| E1 | pretrained_2b / rule | temporal | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | max_speed | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | min_clearance | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | min_entry_delay | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | cruise_stop | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | lane_change | candidate_scalars | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | position_hold | interval_maxima | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_2b / rule | position_hold | xy_waypoints | arm_input | 0.00% | 0.00% | 100.00% |
| E1 | pretrained_8b / rule | temporal | candidate_scalars | arm_input | 27.08% | 68.75% | 0.00% |
| E1 | pretrained_8b / rule | max_speed | candidate_scalars | arm_input | 60.42% | 39.58% | 0.00% |
| E1 | pretrained_8b / rule | min_clearance | candidate_scalars | arm_input | 54.17% | 45.83% | 0.00% |
| E1 | pretrained_8b / rule | min_entry_delay | candidate_scalars | arm_input | 50.00% | 50.00% | 0.00% |
| E1 | pretrained_8b / rule | cruise_stop | candidate_scalars | arm_input | 50.00% | 25.00% | 0.00% |
| E1 | pretrained_8b / rule | lane_change | candidate_scalars | arm_input | 75.00% | 0.00% | 0.00% |
| E1 | pretrained_8b / rule | position_hold | interval_maxima | arm_input | 70.31% | 7.03% | 0.00% |
| E1 | pretrained_8b / rule | position_hold | xy_waypoints | arm_input | 35.94% | 33.59% | 20.31% |
| E2 | 2b / ce_no_rule | temporal | candidate_scalars | arm_input | 49.86% | 19.58% | 0.00% |
| E2 | 2b / ce_no_rule | temporal | candidate_scalars | common_rule | 50.14% | 17.92% | 0.00% |
| E2 | 2b / ce_rule | temporal | candidate_scalars | arm_input | 98.47% | 1.11% | 0.00% |
| E2 | 2b / semantic_no_rule | temporal | candidate_scalars | arm_input | 50.00% | 0.00% | 0.00% |
| E2 | 2b / semantic_no_rule | temporal | candidate_scalars | common_rule | 50.00% | 0.00% | 0.00% |
| E2 | 2b / semantic_rule | temporal | candidate_scalars | arm_input | 97.64% | 0.83% | 0.00% |

## 해석 범위

E1은 기존 테스트 입력의 추가 학습 없는 비교다. E2는 두 과제 모두 같은 사전학습 모델에서 새 LoRA를 시작하므로, 과거 위치 유지의 temporal 어댑터 연속 학습과 초기화 이력이 다르다.

Semantic loss는 Xu 등의 원리에 기반한 범주형 A–D 적용이며, 원 논문 실험의 재현이 아니다. 허용 레이블의 조건부 확률 합에만 적용하므로 임의 출력이나 실행 안전을 보장하지 않는다.

https://proceedings.mlr.press/v80/xu18h.html
https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
