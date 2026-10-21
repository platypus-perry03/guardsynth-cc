# 실제 문서에 근거한 제약 조합 진단

소유 프로젝트: `guardsynth-coc`

599 ms 운영자 기한은 실제 문서의 조건이 아니므로, 앞선 합성 경계 검사와 구분하여 다음 사례를 구성했다. 공식 문서 8건의 원문과 적용 범위를 검토했고, UNECE 문서 2건은 직접 접근이 막혀 실행 근거에서 제외했다. 실제 정책의 일부와 명시한 가정으로 구성한 진단이며, 사고 재현·자연 발생 빈도·주행 모델 성능 실험이 아니다.

## 출처 검토

| ID / 문서 | 확인한 근거와 위치 | 채택 범위 |
|---|---|---|
| ntsb2019: [Collision Between Vehicle Controlled by Developmental Automated Driving System and Pedestrian, Tempe, Arizona, March 18, 2018](https://www.ntsb.gov/investigations/AccidentReports/Reports/HAR1903.pdf) | The former Uber ADS suppressed braking for one second after detecting an emergency to verify the hazard, consider an alternative path, or allow operator takeover. NTSB describes emergency recognition 1.2 seconds before impact and suppression ending 0.2 seconds before impact. Avoidance already required braking beyond ADS design specifications at recognition; the system also lacked maximum-braking-only mitigation when avoidance was impossible. / Printed pp. 13-14, 16-17, 30, 40-41; PDF pages 25-26, 28-29, 42, 52-53 (one-based) | MODELED_POLICY_BRANCH: Historical system design, not a present requirement. The experiment selects an already-triggered emergency branch with a persistent hazard, no takeover and no alternative path. The original trigger involved required deceleration above 7 m/s^2 or jerk magnitude above 5 m/s^3; trigger eligibility and jerk are not modeled. It does not reproduce Tempe or claim suppression removal would have avoided that crash. |
| fhwa2009: [Guidance Memorandum on Consideration and Implementation of Proven Safety Countermeasures](https://highways.dot.gov/safety/proven-safety-countermeasures/guidance-memorandum-consideration-and-implementation-proven) | A yellow interval inconsistent with operating speed can create a dilemma zone where a driver can neither stop safely nor reach the intersection before red. The guidance uses a kinematic timing model with reaction time at least one second and average deceleration at most ten feet per second squared. / Section 7: Yellow Change Intervals, Description and Guidance Statement/Application | MODELING_GUIDANCE: Historical engineering guidance, not a universal legal rule or a measured autonomous-vehicle reaction time. The experiment uses the one-second assumption and a conservative rounded nominal deceleration of 3 m/s^2, not an emergency-braking limit. |
| fhwa2008: [Traffic Signal Timing Manual](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm) | The manual explains differing permissive and restrictive yellow laws and kinematic change-interval calculations. Under permissive yellow, entry can occur during yellow and clearance can continue during red; local statutes determine interpretation. / Chapter 5, section 5.3.2, Yellow Change; equation 5-2 and permissive/restrictive yellow-law discussion | MODEL_AND_JURISDICTION_BOUNDARY: We test reaching the stop line before red, not clearing the entire intersection before red. Constant approach speed, a level road, and a two-action stop/proceed abstraction are declared assumptions. |
| waymo2026: [Jaguar I-PACE Emergency Response Guide and Law Enforcement Interaction Protocol](https://storage.googleapis.com/gweb-mobius-waymo-cdn/waymo/uploads/0186190d983d81f3b54485f05b03bc27c4bacf58.pdf) | The guide says autonomous driving is prevented by a deployed airbag, an open door, Park, or an applied parking brake. It separately says a vehicle remains stationary for a traffic stop and describes confirmation that autonomous operations may resume after the stop. / pp. 13, 17 (PDF pages 13, 17, one-based) | MANUFACTURER_INTERLOCK: The interlock is about driving autonomously; the document explicitly warns that vehicles may still roll or move. Candidate move/hold requests and boolean scene states are authored test inputs, not logged Waymo commands. Absence of these blockers does not establish general driving permission or safety. |
| highway129: [The Highway Code: Rule 129](https://www.gov.uk/guidance/the-highway-code/general-rules-techniques-and-advice-for-all-drivers-and-riders-103-to-158#rule129) | Crossing or straddling double white lines with a solid nearer line is generally prohibited. Crossing is permitted when necessary to pass a stationary vehicle if the road is clear. Additional exceptions concern premises/side roads and specified slow road users. / Rule 129 | EXCEPTION_PRESERVATION: The restricted model fixes all other exceptions false and retains the stationary-vehicle exception. Permission to cross is not an obligation to cross. The unconditional-prohibition variant is an intentionally faulty transcription, not the actual rule. |
| cruise2023: [Part 573 Safety Recall Report 23E-086](https://static.nhtsa.gov/odi/rcl/2023/RCLRPT-23E086-7725.PDF) | After the October 2 collision the vehicle stopped, mischaracterized the event as lateral, and attempted a pullover that dragged the pedestrian. The report describes a corrected response that would have remained stationary in this incident. / pp. 2-4 | QUALITATIVE_ONLY: The full decision guard is not disclosed. This supports studying applicability and transitions, not extracting a universal lateral-collision-implies-pullover policy or reconstructing the controller. |
| highway219: [The Highway Code: Rule 219](https://www.gov.uk/guidance/the-highway-code/road-users-requiring-extra-care-204-to-225#rule219) | Drivers should consider an emergency vehicle's route and act to let it pass while complying with traffic signs and avoiding endangering others. / Rule 219 | REJECT_UNGUARDED_CONFLICT: It supplies no unconditional instruction to enter a red-light intersection or move immediately. Such a mandatory deadline would be fabricated. |
| cfr39210: [49 CFR 392.10: Railroad grade crossings; stopping required](https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-392/subpart-B/section-392.10) | Specified commercial vehicles must stop fifteen to fifty feet before railway tracks and check for approaching trains; listed exceptions include directions to proceed by a police officer or flagman and certain green signals permitted by local law. / Paragraphs (a), (a)(1)-(6), and (b) | SCOPE_CHECK_ONLY: It is not a stop mandate for every autonomous passenger car. Vehicle class and exceptions must be retained; we do not combine it with unrelated jurisdictions to manufacture a conflict. |
| unr152: [UN Regulation No. 152, original 2020 edition](https://unece.org/fileadmin/DAM/trans/main/wp29/wp29regs/2020/R152e.pdf) | 직접 원문 확인 미완료 / Candidate paragraph 5.2.1.1 | RETRIEVAL_INCOMPLETE: Official search index suggests a conditional warning lead time, with an exception for late anticipation. Direct PDF retrieval returned HTTP 403. The original clause and current amendments were not fully verified; excluded from executable cases and manuscript claims. |
| unr157: [UN Regulation No. 157, ALKS](https://unece.org/sites/default/files/2023-12/R157e.pdf) | 직접 원문 확인 미완료 / Candidate paragraphs 5.4.2.1, 5.4.4.1 and 5.5.1 | RETRIEVAL_INCOMPLETE: Planned-operation-end, transition-demand and minimum-risk-manoeuvre timing were investigated. Official PDF retrieval returned HTTP 403. Drafts and secondary copies were not substituted for a verified final edition; no numerical requirement is used in this experiment. |

## 서로 다른 출처 역할의 자연어·정형 명세

문서의 조건, 작성한 상태 입력/후보, 모델링 가정, 검사 목표를 따로 기록한다. 서로 다른 발행기관의 실제 정책들이 그 자체로 모순이라는 주장이 아니다. 아래 수식은 SI 단위로 표시하며 실행은 정수 ms/mm 및 분모 제거를 사용한다. 정지 거리는 mm 격자로 위쪽 반올림하여 경계에서 낙관적인 허용을 만들지 않는다.

### suppression

가정 및 상태: `{"speed_m_s": 10, "deceleration_m_s2": 5, "delay_ms": 1000, "obstacle_mm": 19999}`.

| 출처 / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| ntsb2019 / DOCUMENTED_POLICY_BRANCH | In the persistent-hazard/no-takeover/no-evasion branch, braking begins no earlier than 1000 ms after recognition. | $t_b\ge 1000/1000$ |
| authored:constant_deceleration / MODELING_ASSUMPTION | Assume constant speed until braking and constant deceleration afterwards on a level road; no evasive path. | $x_{stop}\ge v t_b+v^2/(2a)$ |
| authored:avoidance_goal / AUTHORED_REQUIREMENT | For this hypothetical state, stop within 19999 mm of recognition. | $x_{stop}\le 19999/1000$ |
### yellow

가정 및 상태: `{"speed_m_s": 15, "deceleration_m_s2": 3, "reaction_ms": 1000, "yellow_ms": 3000, "distance_mm": 45001}`.

| 출처 / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| fhwa2009 / DOCUMENT_INFORMED_MODEL | The stop branch must reach rest before the stop line under the declared reaction time and nominal deceleration. | $b\Rightarrow d\ge v\rho+v^2/(2a)$ |
| fhwa2008 / DOCUMENT_INFORMED_MODEL | The constant-speed proceed branch must reach the stop line by the yellow endpoint in this closed-boundary timing abstraction. | $\neg b\Rightarrow d\le vY$ |
### interlock

가정 및 상태: `{"door": false, "park": false, "parking_brake": false, "airbag": true, "drive": true}`.

| 출처 / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| waymo2026 / MANUFACTURER_POLICY | An open door, Park, applied parking brake, or deployed airbag prevents autonomous driving. | $(o\lor p\lor k\lor a)\Rightarrow\neg m_{auto}$ |
| authored:candidate_request / AUTHORED_CANDIDATE | Evaluate a candidate that drives autonomously. | $m_{auto}=\top$ |
### exception

가정 및 상태: `{"stationary": true, "necessary": true, "clear": true, "cross": true, "faithful": false}`.

| 출처 / 역할 | 자연어 명세 | 정형 명세 |
|---|---|---|
| highway129 / DELIBERATE_OMITTED_EXCEPTION_FAULT | Faulty transcription: prohibit crossing unconditionally, omitting the stationary-vehicle exception. | $\neg c$ |
| authored:candidate_request / AUTHORED_CANDIDATE | Evaluate a candidate that crosses the line. | $c=\top$ |

## 결과

| 계열 | 사례 | SAT | UNSAT | 질의 | 모든 쌍 SAT인 전체 모순 |
|---|---:|---:|---:|---:|---:|
| suppression | 48 | 30 | 18 | 384 | 12 |
| yellow | 64 | 54 | 10 | 256 | 0 |
| interlock | 32 | 17 | 15 | 128 | 0 |
| exception | 32 | 17 | 15 | 128 | 0 |

총 176개 구성, 896개 질의. UNKNOWN 0, 독립 판정 불일치 0, 잘못된 SAT 해 0/832.

## 사례별 해석

- **제동 억제:** 1초 정책, 일정 감속 가정, 정지 거리 목표를 함께 검사한다. 지연 없이도 목표를 달성할 수 없는 상태를 따로 포함하므로 모든 모순을 지연 탓으로 세지 않는다. 문서의 실제 Tempe 상태에서는 이미 설계 제동 한계로 회피가 어려웠다는 설명을 유지한다. 0초 지연 대조는 가상 상태의 비교이지 실제 사고 회피 주장에 쓰지 않는다.
- **황색 신호:** 선택지가 일정 속도 진행/명목 감속 정지로 제한될 때 두 선택 모두 배제되는 구간을 확인한다. 실제 긴급 제동·가속·회피 가능성까지 배제한 결과가 아니다. 노란 신호 종료 시각의 등호는 닫힌 경계 계산 관례이며 실제 법률상 황색/적색 순간의 해석으로 주장하지 않는다.
- **이동 차단:** 제조사 인터록과 이동 후보의 양립 가능성을 검사한다. 홀드 후보는 16개 상태 모두 SAT다. 차량의 굴러감/견인까지 금지하는 명세로 확대하지 않는다.
- **예외 보존:** 모든 예외 조건이 참일 때 충실한 명세는 횡단 후보를 허용하고, 예외를 삭제한 변형은 이를 배제한다. 횡단을 요구하지 않는 후보는 둘 다 SAT다. 원래 도로 규칙 간 모순이 아니라 누락된 예외의 효과다.

## 기록의 한계

SOURCE_CATALOG.json은 사람이 확인한 URL·판본·문단·해석 범위를 보관한다. 원문 PDF의 바이트 복사본과 해시를 확보한 보존본은 아니다. 법규의 모든 조항, 자연어 자동 추출, 현장 상태의 타당성, 연속시간 안전은 검사하지 않는다. 출처 종류가 다른 입력들을 함께 검사할 수 있음을 보이며, 실제 운영 로그에서 충돌 정책을 발견했다는 뜻은 아니다.
