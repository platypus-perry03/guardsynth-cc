# IEEE Access 원고 수정 목록

IEEE Access 영문 원고의 검토사항과 반영 결과를 관리한다. R01–R18은 사용자 요청에 따라 2026-10-05에 1차 일괄 반영하고 검증했다. 아래 제안 문구와 위치·번호는 검토 당시의 기록이며, 실제 반영 문구와 개편 후 위치는 집필 원문 및 현재 PDF를 기준으로 확인한다. 추가 검토사항은 이 목록에 이어서 기록한다.

- project_id: `guardsynth-coc`
- 기록일: 2026-10-05
- 상태: R01–R41 반영·검증 완료 (2026-10-07)
- 집필 원문: [영문 방법론](IEEE_ACCESS_METHODOLOGY_V01_EN.md), [영문 실험·결과](IEEE_ACCESS_EXPERIMENTS_V01_EN.md), [통합 LaTeX](main.tex)
- 검토 기준: [현재 영문 원고](main.tex)

## 2차 일괄 반영 결과 — 2026-10-05

미반영 R21–R25·R27–R28·R30–R32를 반영하여 R01–R32를 모두 완료했다. 사용자가 현재 TeX에 직접 작성한 대기 규칙 설명과 모델 평가·SMT 비교 문단을 보존하고 집필 Markdown 및 통합 TeX에 동기화했다. 아래의 제안 문구와 과거 표 번호는 검토 이력이며, 현재 대응은 다음과 같다.

| 항목 | 현재 반영 위치·내용 |
|---|---|
| R21 | IV.E.1: Figure 4를 참조하여 두 CNL 문장의 역할과 경계값·필요조건을 설명 |
| R22–R23 | IV.E.3: 내부 장면 번호 제거, STOP 근거 구분, P0·P1·P2 입력 조건 정의 및 실험 절 연결 |
| R24–R25 | IV.F: Table 7 소개, 제공 규칙 → 계약 필드 → 논리식 → 후보 입력 → 판정, 계약 값과 환경 입력 구분 |
| R27 | IV.F: 후보의 허용성 검사, 기준 정답 계산, 모델 정확도·위반 평가, 구현 대응 검사를 쉬운 문단으로 분리 |
| R28 | 내부 구현 파일·패키지를 나열한 소절 제거, 기존 집필 근거 링크와 실제 실행 기록 보존 |
| R30 | V.A.1–2: 데이터 생성·분할 소절, Table 9 규모 표, 학습 설정 소절 추가 |
| R31 | VI.A: 실험 목적과 Table 10 안내, 모델 평가를 먼저 설명하고 SMT 대응 검사를 보조 검사로 소개 |
| R32 | VI.A: Table 10 및 Figure 5 참조, 보충자료 S2·S8에 완료율·후보별 오류 근거 연결 |

새 데이터 규모 표에 따라 기존 주 결과표·명세 검사표·미관측 조건표는 각각 Table 10·11·12가 되었다. Table 7·8과 Figure 4·5의 번호는 유지된다. 본문은 자동 LaTeX label 참조를 사용한다.

두 차례 PDF 컴파일에 성공했으며 분량은 18쪽에서 19쪽으로 증가했다. 그림 7개·표 12개이고 미해결 참조·인용, 누락 문자, 새 본문 넘침은 없다. 12·14–19쪽에서 CNL 설명, 과제 매핑, 데이터·학습 설정, 결과표·그림과 마지막 페이지 배치를 확인했다. 기존 첫 페이지 넘침 2건 및 템플릿 폰트·색상 경고는 유지된다.

기존 세 결과표의 수치, 서론·배경·논의·결론, 한글·보충자료 및 보존 대상 209개 파일의 해시를 확인했다. 이 수에는 빌드가 보호하는 149개와 추가 실험 worktree의 읽기 전용 근거 60개가 포함된다. 실험 실행·데이터·예측 결과를 변경하거나 새 학습 결과를 생성하지 않았다. 파일명 검사에는 수정 파일의 문제가 없고 기존 범위 밖 10건만 남아 있다. 공개 코드·데이터 위치와 제출용 메타데이터 확인은 원고 수정 항목과 별도의 제출 준비 사항이다.

## R01 행동 제약 설명과 Table 2 연결

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.B.1 `Scope and Elements`의 행동 제약 정의 문단과 바로 뒤 EBLC 요소 설명 문단이다.

`A behavioral constraint restricts available actions in a situation.`으로 시작하는 문단은 관찰·행동 이유·행동 제약·선택 목표를 구분하는 개념적 출발점이다. 뒤의 EBLC 문단과 Table 2는 그 행동 제약을 대상·범위·행동 제한·유지·해제·근거 등의 명세 요소로 구체화한다. 따라서 서로 연결되는 설명이며, 현재 Table 2를 명시적으로 참조하는 본문 문장은 없다.

앞의 보행자 예제와 EBLC 요소 설명은 유지하고, EBLC 문단에서 Table 2가 요소의 역할과 시간 프로파일의 구체화를 요약한다는 연결 문장을 추가한다. 표에 LaTeX label을 부여하고 본문에서는 `Table~\ref{...}`로 참조하여 번호를 직접 고정하지 않는다.

## R02 IV.C.1의 보행자 예제 반복 축소

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.C.1 `Separating Candidate Constraints from Evidence`에서 `Not every CoC sentence becomes a constraint.`로 시작하는 문단이다.

이 문단은 IV.B.1에 추가한 예제와 거의 같은 구분을 다시 설명한다.

| 역할 | IV.C.1에서 반복되는 예제 |
|---|---|
| 관찰 | A pedestrian is crossing |
| 행동 이유 | Yield to protect the pedestrian |
| 행동 제약 후보 | Do not enter while the zone is occupied |
| 선택 목표 | Choose the admissible candidate with greatest progress |

네 가지 예제의 상세 설명은 IV.B.1에 남긴다. IV.C.1에서는 반복 예제를 줄이고, 모든 CoC 문장이 제약 후보가 되는 것은 아니라는 추출 원칙과 근거에 없는 임계값·해제 조건을 만들어서는 안 된다는 내용을 유지한다. 필요하면 앞에서 설명한 구분을 짧게 참조한다.

IV.B.2 `Contract Definition and Interpretation`의 허용 가능한 행동 집합과 독립적인 선택 목표에 대한 수학적 설명은 유지한다. 이 부분은 개념 예제를 다시 나열하는 대신 허용성 판단과 최적화의 관계를 정식화한다.

## R03 Table 2와 Table 3 및 Table 4의 캡션 구분

- [x] 반영·검증 완료 (2026-10-05)

세 표의 캡션이 현재 모두 `Constraint representation and example mappings`로 같다. 실제 역할은 다르므로 각각을 구분한다. 아래 캡션은 일괄 수정 시 사용할 제안 문구이다.

| 현재 표 번호 | 실제 내용 | 제안 캡션 |
|---|---|---|
| Table 2 | EBLC 요소의 명세 역할과 시간 프로파일 예제 | EBLC elements and their temporal instantiation |
| Table 3 | 후보 A–D의 진입 시점·진행량 및 0.5초·1.5초 대기 규칙에 따른 허용성 | Action-candidate admissibility under alternative waiting requirements |
| Table 4 | CoC·관찰·규칙·모델링 결정에서 선택한 정보와 명세상의 목적지 | Source content and its mapping to specification inputs |

## R04 시간 제약식의 심볼을 첫 사용 전에 정의

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.B.3 `Temporal Syntax and Semantics`에서 `Evaluation separately binds`로 시작하는 문단과 바로 뒤의 시간 제약식이다.

심볼 정의가 완전히 빠진 것은 아니다. 뒤의 `Writing`으로 시작하는 문단에서 `tau = clear_ms`, `Delta = release_clear_ms`, `u = entry_ms`, `e = enters`를 정의한다. 그러나 첫 제약식에서는 이 대응 관계를 아직 제시하지 않아 독자가 심볼의 의미를 추론해야 한다.

다음 대응 관계를 첫 제약식 앞에서 정의하고, 뒤의 정의는 중복되지 않도록 정리한다. 시점과 기간의 차이 및 `ms` 아래첨자의 단위도 설명한다.

| 심볼 | 구현 이름 | 의미 | 값의 역할 |
|---|---|---|---|
| `tau_ms` | `clear_ms` | 구역이 비워진 시점 | 환경 상태에서 주어지는 검증 입력 |
| `u_ms` | `entry_ms` | 후보의 구역 진입 시점 | 행동 후보에서 주어지는 검증 입력 |
| `Delta_ms` | `release_clear_ms` | 비워진 뒤 요구되는 최소 대기기간 | EBLC 계약에 명시된 규칙의 매개변수 |
| `e` | `enters` | 후보가 구역에 진입하는지 여부 | 행동 후보에서 주어지는 Boolean 검증 입력 |

## R05 EBLC 계약 필드와 Core 변수 및 질의 대입 구분

- [x] 반영·검증 완료 (2026-10-05)

위치는 같은 절의 Code Box 1 설명, 평가 입력 문단 및 `enters = false` 예제이다. 구현 근거는 [시간 프로파일의 contract, lower, verify 함수](../../experiments/paper1_cnl_learning/temporal_preservation.py)이다.

본 논문의 시간 프로파일에서 이 세 단계는 구분된다.

| 단계 | 실제 내용 |
|---|---|
| EBLC 계약 JSON | `hold`, `release_clear_ms`, 대상·단위·가정·출처 등을 명시한다. Code Box 1과 `contract()` 출력에는 `enters` 필드가 없다. |
| Core로 변환 | `lower()`가 `enters`를 Boolean으로, `clear_ms`와 `entry_ms`를 정수로 선언하고 진입 여부를 전제로 하는 시간 제한식을 생성한다. |
| 검증 질의 구성 | `verify()`가 각 질의에서 환경 시점·후보 진입 시점·진입 여부를 등식으로 대입한다. `enters = false`는 해당 후보가 진입하지 않는다는 입력값이다. |

`enters = false`가 계약에 기재된 고정 규칙처럼 읽히지 않도록 이 단계들을 본문에서 명시한다. 이는 후보의 행동 정보를 질의에 대입하는 것이며, 진입하지 않는 후보는 해당 함의식의 전제가 거짓이므로 이 진입 제한을 위반하지 않는다. 선택 목표에 대한 진행량 평가는 별도로 유지한다.

예를 들어 다음 취지의 설명을 추가한다. 이 문구는 검토 당시 제안이다.

> The Boolean `enters` is declared by the temporal profile's Core lowering and is assigned from the candidate being checked; `enters = false` denotes a non-entering candidate rather than a contract field.

이 설명을 위해 기존 EBLC 계약 JSON에 `enters` 필드를 추가하지 않는다. 현재 구현에서 계약 규칙과 질의별 입력이 구분되어 있다는 점을 문서화한다.

## R06 정성 프로파일의 truth와 active 관계 명확화

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.B.4 `Qualitative Lifecycle Semantics`의 첫 정의 문단과 Code Box 2이다. 구현 근거는 [정성 행동 계약의 Core 변환](../../../../platforms/eblc-bcv/src/guard_synth_eblc/action_contract.py)이다.

첫 문단은 `truth[j,t]`와 `active[j,t]`를 각각 정의하지만 두 변수 사이의 관계를 바로 설명하지 않는다. 관계와 갱신 규칙은 이미 Code Box 2와 뒤 문단에 기술되어 있다. 새 규칙을 추가하기보다, 정의 문단과 코드 뒤 설명을 Code Box 2의 변수·각 줄에 맞춰 재작성하고 반복 설명을 통합한다.

`truth[j,t]`는 관찰 근거에 따른 제한 조건의 평가값이며 TRUE·FALSE·UNKNOWN·CONFLICT 중 하나이다. `active[j,t]`는 그 평가값과 근거의 유효성 및 이전 활성 상태를 반영한 의무의 Boolean 상태이다. 아래 표는 Code Box 2를 확인하기 위한 검토용 정리이며, 원고에 추가할 별도 규칙표가 아니다.

| 근거 유효성 | 현재 truth | 현재 active |
|---|---|---|
| 유효 | TRUE | 활성으로 설정 |
| 유효 | FALSE | 비활성으로 설정 |
| 유효 | UNKNOWN 또는 CONFLICT | 이전 활성 상태 유지 |
| 무효 | 모든 값 | 이전 활성 상태 유지 |

예를 들어 보행자 점유가 유효한 근거로 확인되어 진입 금지가 활성화된 뒤 관찰이 UNKNOWN으로 바뀌면, 점유 해소가 확인되지 않았으므로 의무는 활성 상태를 유지한다. 첫 단계에서는 이전 상태를 `prior_active` 입력으로 정하고, 이후에는 직전 단계의 `active`를 사용한다.

비활성 상태와 진입 허용 여부도 구분한다. 처음부터 비활성이었더라도 현재 근거가 UNKNOWN이면 `active`는 비활성을 유지하지만 현재 해소 확인인 `clear`는 성립하지 않는다. 따라서 해당 상태만으로 진입을 허용하지 않는다. 진입 허용은 모든 의무의 현재 해소 확인을 요구하는 별도 정책으로 설명한다.

### Code Box 2와 연결하는 재작성 방향

정의 문단 → 기존 Code Box 2 → 각 줄의 해석 → 기존 생애주기 예제와 진입 허용 정책 순서로 정리한다. 코드의 의미를 유지하면서 주변 설명의 배치와 연결을 수정한다.

- 코드 앞에서는 `truth`가 조건의 평가값이고 `active`가 이력에 의존하는 의무 상태임을 구분한다. 현재 `truth`·`valid`·이전 활성 상태를 입력으로 받아 현재 `active`를 정한다는 관계를 Code Box 2에 연결한다.
- 코드 뒤에서는 1행의 `on`이 유효한 TRUE 근거에 따른 활성화 확인, 2행의 `clear`가 유효한 FALSE 근거에 따른 해소 확인임을 설명한다. `truth` 값만으로 활성화나 해제를 확정하지 않는다.
- 3–4행은 각각 활성화와 해제, 5행은 그 외의 경우 이전 상태 유지로 연결하여 읽는다. 처음의 `previous_active`는 `prior_active` 입력이고 이후에는 직전 단계의 `active`임을 같은 설명에서 명시한다.
- 관찰을 읽고 상태를 갱신한 다음 행동을 제한한다는 평가 순서를 유지한다. 첫 문단·Code Box 2 뒤 문단·행별 해설에서 같은 규칙을 여러 번 풀어 쓰지 않도록 통합한다.
- `Evidence is read and activation updated before constraining the action.`은 명세의 상태 갱신·적용 의미를 설명한다는 점을 명확히 한다. 현재 근거 → 현재 의무 상태 → 행동 제한이라는 의존 관계를 정의하며, SMT 솔버의 내부 실행 순서를 설명하는 문장으로 쓰지 않는다. 검증은 이 해석 규칙을 Core/SMT 제약으로 표현하여 주어진 근거·상태 이력·행동 후보가 그 제약과 양립하는지 검사하는 별도 단계임을 구분한다.
- 기존 TRUE → UNKNOWN → FALSE → TRUE 예제를 활용해 UNKNOWN에서 활성 상태가 유지되는 이유를 5행과 연결한다. 같은 내용을 설명하는 새 규칙표나 별도 단계표는 원고에 추가하지 않는다.
- 현재 진입 허용 정책은 모든 의무의 `clear`를 요구한다고 연결한다. 초기 비활성 상태에서 UNKNOWN을 받은 경우에는 5행에 따라 비활성을 유지하지만 2행의 `clear`는 성립하지 않으므로, 비활성만으로 진입을 허용할 수 없음을 설명한다.

코드 앞에 넣을 연결 문장의 취지는 다음과 같다. 검토 당시의 제안이다.

> Code Box 2 maps the current condition status and evidence validity, together with previous activation, to the current obligation state. Thus, `active[j,t]` is a state updated from evidence and history, rather than a direct copy of `truth[j,t]`.

`Evidence is read...` 문장은 명세의 해석 규칙임을 드러내도록 다음 취지로 재작성한다. 검토 당시 제안이며, 주변 Code Box 2 해설과 통합한다.

> At each decision step, the profile defines the current obligation state from the current evidence and previous activation, as specified in Code Box 2. The updated state, together with current clearance evidence, determines the action restrictions at that step. Verification encodes these interpretation rules as constraints and checks whether the supplied evidence and state history and the candidate action satisfy them.

## R07 본문의 내부 코드 라벨을 논문용 구현 출처로 정리

- [x] 반영·검증 완료 (2026-10-05)

범위는 본문에 사용된 S1–S5 코드 링크 라벨 전체이다. 특히 IV.A의 `Implementation evidence is linked in S1 and S2` 문장, IV.B.3의 validator 설명 끝 S1·S3, IV.B.4의 현재 진입 허용 정책 문단 끝 S2를 포함한다.

현재 라벨은 내부 구현 파일에 연결하기 위해 사용된 것이며, 의미와 역할을 소개한 논문용 참조 체계가 아니다. 초반에 S1·S2가 라벨로 등장하더라도 이름과 역할이 정의되지 않아 이후의 S1·S2·S3 등을 독자가 해석하기 어렵다. 아래는 수정 작업을 위한 대응 관계이며 본문에 같은 라벨표를 추가하라는 제안이 아니다.

| 현재 라벨 | 구현 파일 | 뒷받침하는 내용 |
|---|---|---|
| S1 | [temporal_preservation.py](../../experiments/paper1_cnl_learning/temporal_preservation.py) | 시간 계약의 생성·검사·Core 변환·CNL 생성·논리 검증 |
| S2 | [action_contract.py](../../../../platforms/eblc-bcv/src/guard_synth_eblc/action_contract.py) | 정성 프로파일의 상태 갱신과 진입 허용 정책을 Core 제약으로 변환 |
| S3 | [temporal_training_data.py](../../experiments/paper1_cnl_learning/temporal_training_data.py) | 합성 학습 데이터의 확장과 행동 후보 검증 |
| S4 | [qualitative_scene_contract.py](../../src/guard_synth/qualitative_scene_contract.py) | 특정 실제 장면 검토 작업의 조건부 계약 구성과 미확정 근거 관리; 일반 CoC 추출기가 아님 |

사용자 검토에 따라 S1–S5를 설명 없이 본문 끝에 단독으로 붙이는 표기는 정리한다. 본문은 명세·해석·검증 방법을 자체적으로 이해할 수 있게 작성하고, 논문 안에서 정의한 Code Box·표·절을 필요한 위치에서 참조한다. 예를 들어 validator 문단은 지원 버전·허용 필드 조합·지원 대기기간·학습 데이터 사용 범위를 설명하도록 완결하며, 끝의 S1·S3 내부 라벨에 설명을 의존하지 않는다.

구현 근거의 추적 가능성은 유지한다. 파일 이름과 역할, 버전 및 접근 경로는 코드 제공 안내나 부록·보충자료에서 일관되게 정리하고, 본문에서는 해당 안내를 설명 가능한 참조로 연결한다. 작성자 환경의 절대 파일 경로는 제출·공유본의 코드 출처로 사용하지 않는다. 공개 코드 주소나 부록·보충자료의 번호가 확정되지 않은 상태에서 이를 만들어 넣지 않는다. 기존의 S2만 최초 등장 시 이름을 붙이는 제안은 이 전체 표기 정리 방향으로 대체한다.

## R08 생애주기 명세와 실제 평가 범위 구분

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.B.2의 계약 해석, IV.B.3의 시간 프로파일, IV.B.4의 정성 생애주기 설명과 이들을 연결하는 평가 범위 설명이다.

이전 활성 상태를 사용하는 정성 생애주기 설명이 주요 학습 실험의 행동 평가에도 그대로 적용되는 것으로 읽히지 않도록 범위를 구분한다. 반대로 정성 프로파일을 아직 구현·검사하지 않은 향후 명세로만 설명해서도 안 된다.

| 경로 | 이전 활성 상태 사용 | 확인된 평가 범위 |
|---|---|---|
| 주요 시간 프로파일 학습·행동 평가 | `prior_active`나 단계별 `active`를 사용하지 않음 | 비워진 시점·후보 진입 시점·진입 여부와 계약의 대기기간으로 시간 제약을 검사함. 단일 해소 전환과 재점유 없음 가정 아래 시간 경과를 표현함. |
| 별도 정성 계약 검증 | 초기 `prior_active`와 이전 단계의 `active`를 사용함 | Core에 초기·전이 제약을 생성하고 UNKNOWN에서의 유지, 무효 근거에 의한 해제 방지, 해제 후 재활성화를 SMT 질의로 검사함. |
| 실제 영상의 상태 이력 검증 | 위의 조건부 검사만으로 관찰 기반 이력 검증을 입증하지 못함 | 정성 실행 기록은 출처 확인이 미완료인 조건부 계약이며 실제 관찰된 이전 상태·근거 이력의 정확성을 검증한 결과로 확대하지 않음. |

구현 근거는 [시간 후보 검증](../../experiments/paper1_cnl_learning/temporal_training_data.py), [정성 Core 상태 전이](../../../../platforms/eblc-bcv/src/guard_synth_eblc/action_contract.py), [정성 계약 검사 질의](../../experiments/paper1_cnl_learning/action_contract.py)이다. 정성 실행 결과 (superseded run removed; see artifact migration catalog)와 질의별 결과 (superseded run removed; see artifact migration catalog)에서는 전체 25개 질의가 예상 판정과 일치하며, 이전 상태 유지·무효 해소 근거·재활성화 검사도 실제로 수행된 것을 확인할 수 있다. 이는 주어진 전제에 대한 명세 검사 범위로 설명한다.

`주어진 초기 상태와 구성된 근거 이력에 대한 조건부 명세 검사`라는 표현이 이전 상태를 추적할 수 있게 되면 향후 검증하겠다는 계획처럼 읽히지 않도록 재작성한다. 여기서 조건부는 지정한 입력과 가정 아래 성립하는 검사라는 뜻이며, 검사의 실행 여부를 미루는 조건이 아니다. 초기 `prior_active`와 단계별 `truth`·`valid` 값을 검사 입력으로 지정하고, 그 입력에 따른 `active`의 유지·해제·재활성화가 명세와 일치하는지 이미 검사했다. 실제 영상에서 과거 활성 상태를 관측·추적하여 입력값의 정확성을 검증한 것은 아니라는 한계는 별도로 명시한다.

예를 들어 이전 활성 상태를 true, 현재 근거값을 UNKNOWN으로 지정한 질의에서 현재 활성 상태를 false로 놓으면 UNSAT가 된다는 검사 기록이 있다. 이는 주어진 초기값에 대한 상태 유지 규칙을 실제로 검사한 사례이다.

일괄 반영 시 다음 취지로 서술한다. 검토 당시 제안이다.

> We checked the lifecycle rules using specified initial activation values and constructed sequences of evidence-status inputs. The executed SMT queries test persistence, release, and reactivation under these inputs. These checks do not establish that the initial states or input sequences were correctly recovered from real-scene video.

정성 프로파일에서도 의무 상태의 전이와 현재 진입 허용 정책은 구분한다. 의무 상태는 이전 상태에 의존하지만, 진입 허용은 현재 모든 의무의 해소 확인을 요구한다. 과거 비활성 상태만으로 현재 진입을 허용하지 않는다.

## R09 제약의 의미 검증과 학습 정답 생성의 목적 명시

- [x] 반영·검증 완료 (2026-10-05)

위치는 GuardSynth의 EBLC 명세 → 논리 검증 → CNL 표현 → CoC 추가 흐름을 설명하는 문단, IV.B.3의 validator 문단과 시간 후보 검사 설명, 학습 데이터 구성 설명이다. 구현 근거는 [시간 계약의 validate·verify·render](../../experiments/paper1_cnl_learning/temporal_preservation.py)와 [후보 판정 및 학습 정답 생성](../../experiments/paper1_cnl_learning/temporal_training_data.py)이다.

우리 접근은 CoC에 추가할 행동 제약을 EBLC로 명세하고, 그 명세의 허용·불허 판정이 의도한 규칙과 일치하는지 검사한 뒤 CNL로 표현하여 CoC에 추가하는 것이다. EBLC는 올바른 행동과 잘못된 행동을 각각 나열하는 대신 둘을 구분하는 규칙을 담는다. 검증에서는 허용되어야 하는 후보가 허용되는지와 배제되어야 하는 후보가 배제되는지를 모두 확인한다.

다음 세 역할을 구분하여 설명한다.

- 프로파일 검사: `validate()`가 지원 버전과 고정된 필드 조합 및 대기기간을 검사한다. 이 구조 검사를 행동 의미 검증과 혼동하지 않는다.
- 행동 의미 검사: 환경 정보와 행동 후보를 Core/SMT 질의에 대입하고, SAT·UNSAT 결과를 독립적인 환경 규칙의 예상 판정과 대조한다. 너무 이른 진입, 대기 경계 및 진입 보류 등을 검사한다. 올바른 후보만 확인하면 대기 조건 누락처럼 불허 후보도 허용하는 오류를 놓칠 수 있으므로 양쪽 판정이 필요하다.
- 학습 정답 생성: 독립적인 환경 규칙으로 허용 후보를 정하고, 그중 진행량이 가장 큰 후보를 정답으로 선택한다. 불허 후보는 선택지와 검사 대상에 포함되지만 학습 정답으로 제공하지 않는다. 후보별 EBLC 검사 결과는 환경 판정과 대조하는 메타데이터이며 학습 정답을 그대로 복사해 검사하는 방식이 아니다.

후보 검사에서 불허 판정을 받았다는 사실을 실제 차량이 위반 행동을 실행했다는 뜻으로 서술하지 않는다. 이는 해당 후보를 선택한다면 명세된 제약을 위반한다는 조건부 판정이다. 또한 현재 합성 실험은 별도로 구성한 행동 후보를 사용하며, CoC의 추상적 행동 표현을 자동으로 추출하여 구체적인 시점·행동 값에 연결한 결과로 설명하지 않는다.

본문에 넣을 문구의 취지는 다음과 같다. 검토 당시 제안이며 기존 흐름 설명과 통합하여 반복을 줄인다.

> GuardSynth specifies the behavioral restrictions to be appended to CoC as EBLC contracts. Semantic checks test whether the executable contract admits candidates that should be permitted and rejects candidates that should be excluded under the supplied rules. The checked contracts are rendered as CNL and appended to CoC. Profile validation checks supported versions and field combinations separately from these semantic checks.

> In the synthetic learning experiment, candidate admissibility is determined independently from the supplied environmental rules and compared with the Core/SMT results. Both admissible and inadmissible candidates are included as alternatives, while the training target is the admissible candidate with the greatest progress. Rejection denotes incompatibility of a hypothetical candidate with the contract, rather than an observed driving violation. These checks establish agreement on the constructed cases, not correctness across all possible traffic situations.

## R10 검증할 성질과 구체적인 질의·오류 예제 연결

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.D의 `Properties and Queries`, 기존 검증 성질 표 및 Code Box 3이다. 현재 원고에는 이미 일관성, 제한 적용, 해제 경계 및 진입 보류에 대한 질의와 기대 판정이 있다. 따라서 같은 숫자의 새 표를 추가하기보다 기존 표의 제목·해석과 주변 설명을 재작성하여 독자가 무엇을 검증하는지 바로 이해하도록 한다. 앞의 시간 명세 설명에서 이 표와 Code Box 3을 참조하고, 최종 CoC+CNL 예제인 Table 6까지 연결한다. 표 번호는 label과 참조로 관리한다.

`We distinguish consistency, restriction enforcement, release boundaries, and permissibility.` 문단의 첫머리에서 기존 Table 3의 후보 허용 조건을 기존 Table 5의 검증 성질·질의와 연결한다. 구역 해소가 11.0초일 때 0.5초·1.5초 규칙의 진입 허용 경계가 각각 11.5초·12.5초가 됨은 Table 3과 본문의 조건식으로 설명한다. R17의 중복 축소 방향에 따라 Figure 4 참조를 추가하는 대신 두 표를 label로 참조한다.

문단 첫머리와 기본 SAT의 의미는 다음 취지로 정리한다. 실제 표 번호는 일괄 반영 시 label 참조로 바꾼다.

> Table 3 illustrates the candidate permissions implied by the supplied waiting rules. Table 5 specifies the logical queries used to check consistency, restriction enforcement, release boundaries, and permissibility. A SAT result for the base contract shows that at least one satisfying assignment exists, but that assignment may simply describe non-entry. We therefore also query whether entry is feasible at and after the release boundary.

이 문단의 `satisfying model`과 `entering model`은 학습 VLM이 아니라 논리 조건을 만족하는 변수 대입을 뜻한다. 혼동을 줄이도록 `satisfying assignment`와 `entry is feasible` 등의 표현을 사용한다. 기본 SAT만으로는 진입 가능성을 확인할 수 없으며, 해제 후 진입 가능성 질의는 모든 진입을 막는 명세 오류를 확인하는 역할을 한다. 이 검사가 실제 학습 모델이 진행 후보를 얼마나 선택하는지 평가한 결과를 대신하지 않는다는 설명도 유지한다.

예제의 공통 전제를 먼저 명시한다. 구역이 비워진 시점은 11000ms, 최소 대기기간은 500ms이며, 진입 후보에는 `enters = true`를 대입한다. 진입 조건은 `entry_ms >= 11500`이다. 진입 보류 질의에는 `enters = false`를 대입한다. 아래는 기존 검증 표를 명확히 설명하기 위한 검토용 정리이다.

| 검증할 성질 | 질의 또는 후보 조건 | 기대 판정 | 확인하는 의미와 오류 예 |
|---|---|---|---|
| 명세의 일관성 | 기본 계약에 만족하는 값이 존재하는가 | SAT | 모든 행동을 배제하는 모순이 없는지 확인한다. 이것만으로 진입 가능성까지 확인한 것은 아니다. |
| 대기 조건의 강제 | 계약과 함께 `enters = true`, `entry_ms < clear_ms + 500`을 요구 | UNSAT | 조건보다 이른 진입을 허용하는 반례가 없어야 한다. 대기 조건 누락이나 비교 방향 오류를 확인할 질의이다. |
| 경계 직전 진입 배제 | 11499ms에 진입 | UNSAT | 요구 대기기간보다 1ms 짧은 후보를 배제해야 한다. |
| 경계값 포함 | 11500ms에 진입 | SAT | `at least`와 `>=`의 의미가 일치해야 한다. `>`로 잘못 변환하면 이 후보를 배제한다. |
| 해제 후 진입 가능성 | 11501ms에 진입 | SAT | 조건을 충족한 진입이 가능해야 한다. 진입을 영구히 금지하는 명세는 통과하지 못한다. |
| 진입 보류 허용 | `enters = false` | SAT | 허용 조건이 진입 의무로 바뀌지 않아야 한다. 진입 보류는 별도의 목표 평가를 받는다. |

본문은 각 질의의 SAT·UNSAT가 왜 기대되는지, 반대 결과가 나오면 무엇을 의심해야 하는지 설명한다. 예를 들어 너무 이른 진입 질의의 UNSAT는 후보와 계약의 불일치라는 예상 결과이며 명세 오류 자체가 아니다. 예상 UNSAT 질의가 SAT가 되거나 예상 SAT 질의가 UNSAT가 되면 구현·변환·질의 구성 또는 전제를 점검해야 한다. 위 오류 예는 발견할 수 있는 오류를 설명하는 예시이며, 해당 오류가 실제 원고 구현에서 발견되었다는 실행 결과로 서술하지 않는다.

검증 범위를 질의 종류에 맞게 구분한다. 구체적인 경계 후보 검사는 지정한 값에서 기대 판정과 일치하는지 확인한다. 기존 제한 적용 질의는 시간 변수를 고정하지 않은 기호적 반례 검색으로, UNSAT이면 인코딩된 모델과 가정 안에서 이른 진입 반례가 없음을 뜻한다. 따라서 모든 검사를 유한 후보 사례 확인으로만 축소하지 않되, 그 결과를 실제 영상 해석이나 모든 교통 상황의 안전성 증명으로 확대하지 않는다. R09의 구성 사례에 대한 설명은 후보 대조 검사에 적용하고, 이 기호적 질의의 범위는 별도로 명시한다.

표 앞뒤에 넣을 문구의 취지는 다음과 같다. 검토 당시 제안이며 기존 설명과 통합한다.

> For clearance at 11000 ms and a required wait of 500 ms, the entry threshold is 11500 ms. We check restriction enforcement, inclusion of the release boundary, feasibility after release, and permission to defer. Entry at 11499 ms must be incompatible with the contract, whereas entry at 11500 or 11501 ms and non-entry must remain compatible. These checks test whether the executable specification enforces the intended permission conditions; they do not establish the factual clearance time or the real-world adequacy of the supplied waiting rule.

기대 결과와 오류 예의 관계 및 기호적 질의의 범위는 다음 취지로 설명한다.

> An incorrect strict comparison would reject entry at 11500 ms, while an omitted waiting condition would admit premature entry. The symbolic restriction query additionally searches for any entering assignment earlier than the required release time within the encoded model. An UNSAT result excludes such an assignment under that model and its assumptions.

## R11 EBLC 명세 구성 절차의 목적을 문단 첫머리에 명시

- [x] 반영·검증 완료 (2026-10-05)

위치는 `The procedure identifies action-relevant entities, situations, and rationales in CoC`로 시작하는 명세 구성 문단이다. 현재 첫 문장은 `The procedure`의 목적을 밝히지 않고 세부 단계부터 나열하여, 문단 자체만 읽으면 무엇을 구성하는 절차인지 알기 어렵다.

첫 문장에서 CoC·관찰·제공된 규칙을 이용해 EBLC 명세를 구성하는 절차임을 간단히 밝힌다. 기존 첫 문장의 `The procedure`를 다음과 같이 구체화하면 별도의 개요 문단 없이 목적과 첫 단계를 연결할 수 있다.

> To construct an EBLC specification from CoC, observations, and supplied rules, the procedure first identifies action-relevant entities, situations, and rationales in CoC, then binds entities and zones to observations and identifies the decision time.

한국어 취지는 “CoC·관찰·제공된 규칙으로 EBLC 명세를 구성하기 위해, 먼저 CoC에서 행동 관련 정보를 식별하고 이를 관찰 근거와 의사결정 시점에 연결한다”이다. 뒤의 규칙 적용·유지·해제·시간·가정 명세와 미확정 정보 처리 설명은 이 목적 아래 이어지도록 유지한다. 명세 구성 절차를 소개하는 표현을 사용하고, 현재 합성 실험에서 전체 자동 추출이 구현되었다는 주장으로 바꾸지 않는다.

## R12 명세 구성 입력의 출처와 자동화·사람 확인 범위 설명

- [x] 반영·검증 완료 (2026-10-05)

위치는 `In the primary synthetic experiment, the environment generator and supplied rule provide these inputs.`로 시작하는 문단이다. R11의 명세 구성 절차 뒤에서 합성 실험과 실제 장면 경로의 입력 출처 및 처리 범위를 설명하도록 정리한다.

합성 실험에서는 환경 생성기가 비워진 시점 등의 환경 정보를 제공하고, 별도로 제공된 실험 규칙이 최소 대기기간을 정한다. 자동화는 이 정보를 구조화하고 EBLC·Core/SMT·CNL로 변환하는 역할을 한다. 영상만으로 교통법규나 대기기간을 발견하는 과정으로 설명하지 않는다.

`Environmental clearance and rule duration determine the contract and verification representation.`은 환경 시점과 규칙 기간이 모두 계약 필드인 것처럼 읽힐 수 있다. R04·R05와 맞춰 대기기간 `release_clear_ms`는 EBLC 계약의 규칙 매개변수이고, 비워진 시점 `clear_ms`는 질의별 환경 입력임을 명시한다. 행동 후보의 `entry_ms`와 `enters`도 별도로 질의에 대입한다. 두 종류의 입력을 결합해 후보의 진입 조건을 검사한다는 설명으로 바꾼다.

실제 장면 경로는 대상·구역·사건·규칙 적용 여부를 사람이 확인해야 하는 검토 절차로 설명한다. 현재 어댑터는 특정 scene18 개발 작업에 한정되어 있으며, 미확정 바인딩과 근거는 미확정으로 유지한다. 검토가 필요하다는 사실을 검토가 완료되었다는 결과로 서술하지 않는다. 기존 어댑터는 출처 검토 필요 상태와 `learning_export_allowed = false`를 반환하므로, 일반적인 실제 영상의 자동 계약 생성이나 학습 정답 생성이 완료된 것으로 확대하지 않는다. R08의 실제 근거 이력 검증 범위와도 일치시킨다.

### 실제 장면에서 사람이 개입할 항목과 시점

`human confirmation`이라는 포괄적 표현만 남기지 않고, 사람이 무엇을 확인해야 하는지 본문에서 구체적으로 밝힌다. 다음은 원고 재작성용 역할 정리이며 별도 표를 추가하라는 요구는 아니다.

| 사람의 확인·검토 항목 | 구체적인 확인 내용 | 자동 처리와의 관계 |
|---|---|---|
| 대상·구역 바인딩 | CoC가 지칭하는 대상이 영상의 어느 객체인지, 제한이 적용되는 구역이 어디인지 확인 | 파일의 객체 ID·출처 참조가 있다는 사실만으로 바인딩의 정확성이 확인된 것은 아님 |
| 사건·시점과 해소 근거 | 점유·충돌 조건이 발생하거나 해소되었는지, 이를 어느 시점의 근거가 뒷받침하는지 확인 | UNKNOWN·CONFLICT나 단순한 미관찰을 확인된 해소로 바꾸지 않음 |
| 근거 채택 기준 | 해당 관찰을 유효한 근거로 사용할 기준을 정하고 충족 여부를 확인 | `valid`는 지정된 입력이며 SMT가 영상의 사실성이나 근거의 신뢰성을 판정하는 것은 아님 |
| 규칙 적용·가정 | 어떤 출처의 규칙이 ego와 해당 상황에 적용되는지, 대기기간·해제 조건·모델링 가정의 근거를 확인 | 자동화는 제공된 규칙과 조건을 구조화·변환함; 부족한 수치나 조건을 만들어 넣지 않음 |
| 생애주기 초기 입력 | 이력을 사용하는 경우 초기 활성 상태와 제공할 근거 이력의 출처·정당성을 확인 | 전이 검사는 주어진 초기값과 이력에 대한 검사임; 실제 과거 상태를 복원했다는 증거로 취급하지 않음 |
| 실제 장면의 학습 자료 채택 | 행동 정답의 독립적인 근거와 CNL이 검토된 제약을 표현하는지 확인 | 미확정 입력에서 나온 DEFER를 실제 장면의 정답으로 자동 채택하지 않음; 현재 어댑터에는 행동 정답과 독립 CNL 검토가 미완료 항목으로 남아 있음 |

사람의 확인은 조건부 계약을 만들거나 SMT 질의를 실행하기 위한 일률적인 사전 승인으로 서술하지 않는다. 미확정 입력에 대한 조건부 검사는 가능하지만, 그 입력을 실제 장면에서 확인된 사실로 취급하거나 검토된 학습 자료로 채택하려면 위 근거 확인이 필요하다는 관계로 설명한다. 본문에서 검토 필요 항목과 실제 완료된 항목을 구분하고, 현재 scene18 작업의 미확정 항목은 해결된 것처럼 쓰지 않는다.

S3·S4 내부 코드 라벨과 로컬 절대 경로는 R07의 전체 출처 정리 범위에 포함한다. S4의 파일과 역할을 R07의 검토용 대응표에 보완했으며, 본문에는 입력 출처와 처리 범위를 자체적으로 이해할 수 있는 설명을 남긴다.

문단 재작성의 취지는 다음과 같다. 검토 당시 제안이다.

> In the primary synthetic experiment, the environment generator supplies the clearance time, while a supplied experimental rule sets the required waiting duration. The duration is stored in the EBLC contract; the clearance time and candidate action values are bound separately in verification queries. Automation structures and transforms these supplied inputs into the specification and verification representations. It does not infer traffic laws or waiting durations from video alone.

> For real-scene grounding, human review must establish the correspondence between referenced entities and zones and the scene, confirm event and clearance evidence at the relevant times, and assess evidence acceptance and rule applicability. Review must also establish the basis for timing parameters, modeling assumptions, and any supplied initial lifecycle state. Adopting a real-scene learning example additionally requires an independently justified action reference and review of the generated CNL. The implemented adapter supports one specified development-review task; its unresolved bindings and pending reviews are retained, and learning export remains disabled. Logical checks under supplied inputs do not replace these grounding and data-review steps.

## R13 시간 예제의 행동 후보 A–D 소개·표 참조·합성 점수 부여 설명

- [x] 반영·검증 완료 (2026-10-05)

위치는 `Running Temporal Example`의 후보 표와 `Progress is a synthetic utility`로 시작하는 해설 문단이다. A–D는 기존 Table 3의 행동 후보 라벨이며, A는 10.5초 진입, B는 11.5초 진입, C는 12.5초 진입, D는 진입 보류를 뜻한다. 표에는 이 정보가 있지만 본문에서 라벨을 먼저 소개하지 않고 B·C·D를 사용하며, 표를 번호로 참조하지도 않는다. 표 배치에 따라 해설과 정의가 떨어지면 독자가 의미를 알기 어렵다.

표 전에 가상의 행동 후보 네 개를 비교한다는 문장을 넣고 표를 명시적으로 참조한다. 표에 label을 부여하고 `Table~\ref{...}`로 연결한다. 해설 문단도 첫 문장부터 이 표의 설명임을 밝힌다. 해설에서는 라벨과 행동을 함께 언급하여 `candidate B (entry at 11.5 s)`, `candidate C (entry at 12.5 s)`, `candidate D (deferral)`로 읽히게 한다. R03의 구분된 후보 표 캡션과 함께 반영한다.

표를 소개하는 문구의 취지는 다음과 같다. 검토 당시 제안이며 실제 LaTeX 참조에는 일괄 수정 시 부여한 label을 사용한다.

> We compare four hypothetical action candidates, labeled A–D in the candidate table. Three specify different entry times, and the fourth defers entry. The table gives their synthetic progress scores and admissibility under the two supplied waiting rules.

기존 해설은 다음 취지로 정리한다.

> Table 3 presents a generated data instance, not observed model predictions. It illustrates how the two waiting rules change candidate admissibility. The scores of 110, 100, 85, and 0 are assigned synthetic utilities for ranking permitted candidates. Candidate B (entry at 11.5 s) is admissible under the 0.5-second rule but excluded under the 1.5-second rule; candidate C (entry at 12.5 s) is admissible under both. Candidate D (deferral) satisfies both entry restrictions but has zero progress. The reference action is the highest-scoring admissible candidate: B under the 0.5-second rule and C under the 1.5-second rule. This selection objective is separate from the entry restriction.

사용자 검토에 따라 생성된 데이터 예제라는 성격을 해설의 맨 앞에서 밝힌다. `The table`을 명시적인 Table 3 참조로 바꾸고, 모델 예측 결과와의 구분을 뒤에서 반복하지 않는다.

라벨은 이 예제 안에서만 해당 행동과 대응하며 데이터 전체에서 고정된 행동 종류가 아니라는 설명을 유지한다. 진행량 점수도 실차에서 측정한 거리·속도로 바꾸어 설명하지 않는다.

`Candidate labels rotate`는 데이터 사례를 만들 때 같은 행동 템플릿에 붙는 A–D 라벨을 순환하여 재배정한다는 뜻이다. 예를 들어 한 사례에서 11.5초 진입 후보가 B라면, 라벨을 한 칸 순환한 사례에서는 같은 행동이 C가 될 수 있다. 행동의 진입 시점과 점수는 라벨 재배정만으로 달라지지 않지만 정답의 출력 문자는 달라진다. 이는 모델이 항상 B 같은 고정 문자를 답하는 단서를 줄이려는 설계이며, 문자 회전만으로 다른 수치·텍스트 단서까지 제거되었다고 주장하지 않는다.

위 라벨 회전 설명은 R14에 따라 실험의 데이터 구성 설명으로 옮긴다. `Running Temporal Example`에는 현재 예제에서 라벨과 행동이 어떻게 대응하는지만 설명하고, VLM 학습 설계의 상세 내용은 넣지 않는다.

### Progress Score의 부여 방식과 정답 선택 설명

구현 근거는 [확장 합성 데이터의 records 함수](../../experiments/paper1_cnl_learning/temporal_training_data.py)와 [원 시간 환경의 make_scene·target_for 함수](../../../01-safety-constrained-coc/experiments/vlm_guard_learning/temporal_guard_world.py)이다. 두 생성기 모두 후보 템플릿 순서에 `110, 100, 85, 0`을 고정 배정한다. 진입 시점이나 거리·속도를 넣어 계산하는 점수식은 구현되어 있지 않다. 라벨을 회전해도 점수와 행동 템플릿의 대응은 유지한다.

점수의 역할은 제약으로 허용 집합을 정한 뒤 그 집합 안에서 선택 우선순위를 제공하는 것이다. Table 3에서는 A가 110으로 가장 높아도 두 규칙에서 불허이므로 제외한다. 0.5초 규칙에서는 B·C·D 중 100인 B를, 1.5초 규칙에서는 C·D 중 85인 C를 선택한다. 허용 여부를 점수에서 계산하거나 높은 점수를 안전성 근거로 사용하지 않는다. 정답 선택은 `max(allowed, key=lambda c: c.progress)`이며 별도의 물리적 진행량 산출 결과로 서술하지 않는다.

현재 정답 선택은 허용 후보 사이의 점수 순서에 의존하며, 110·100·85라는 값에 실측 또는 물리 모델의 산출 근거를 부여하지 않는다. 표의 열 제목을 `Assigned synthetic utility score` 등으로 구체화하는 방안도 검토한다. 문단 초안의 `Table 3`은 일괄 반영 시 실제 label 참조로 바꾼다.

Progress Score는 시나리오 ID 같은 식별자나 SMT 상태 변수가 아니라, 실험 설계자가 고정 배정한 후보 선택 평가값임을 설명한다. 현재 최대 점수 선택 기준에서는 후보 간 순서를 유지하는 다른 값으로 바꾸어도 정답은 같다. 예를 들어 `4, 3, 2, 0`을 같은 후보 템플릿에 배정해도 참조 행동은 유지된다. 이는 정답 선택 기준에 대한 설명이며 모델 학습 결과까지 동일하다는 주장은 아니다. 점수는 제약의 허용 여부를 검사하는 SMT 질의에 사용되지 않는다.

### Table 3의 reference 정의

`Admissible; reference`에서 `admissible`은 해당 대기 규칙을 만족하는 허용 후보라는 뜻이고, `reference`는 허용 후보 중 합성 점수가 가장 높아 학습·평가의 기준 정답으로 선택된 후보라는 뜻이다. 참고문헌이나 출처 참조를 뜻하는 라벨이 아니다. B는 0.5초 규칙에서 허용 후보 B·C·D 중 최고 점수이므로 reference이고, C는 같은 규칙에서 허용되지만 reference는 아니다. 1.5초 규칙에서는 B가 불허이며 C가 reference가 된다.

표의 reference를 첫 사용 전에 정의하거나 캡션에서 설명하고, 셀의 표기를 `Admissible; reference action` 등으로 구체화한다. 기준 정답은 독립적인 환경 규칙으로 허용 집합을 구한 뒤 합성 점수로 선택하며, 실제 관측된 운전자 행동이나 모델의 예측 결과라는 뜻으로 쓰지 않는다. R09의 학습 정답 생성 설명과 연결한다.

> In this table, “reference” denotes the action selected as the learning and evaluation target: the candidate with the highest assigned utility among those admissible under the specified waiting rule.

## R14 제약 도출 예제에서 학습 데이터 설계로 넘어가는 흐름 정리

- [x] 반영·검증 완료 (2026-10-05)

위치는 IV.C `Defining and Deriving Behavioral Constraints`의 `Specification Procedure and Automation Scope`, `Running Temporal Example` 및 `What Is Extracted, From Where, and Where It Is Placed`와 IV.E `CNL Generation and CoC Augmentation`, V `Experimental Setup` 사이의 연결이다.

사용자가 지적한 문제는 학습 모델 이름의 누락만이 아니라 절의 설명 목적이 도중에 바뀌는 것이다. 제약을 정의·도출하는 절에서 갑자기 학습 정답 생성과 라벨 회전의 이유를 상세히 설명하면, CoC·관찰·규칙 → EBLC 구성이라는 흐름이 끊긴다. 여기서 Qwen3-VL-2B-Instruct의 이름을 추가하거나 학습 이야기를 더 길게 설명하는 방식으로 해결하지 않는다.

일괄 반영 시 설명의 배치를 다음과 같이 정리한다.

1. IV.C의 시간 예제는 원래 CoC, 제공된 관찰, 별도 규칙, 가정을 계약 필드와 검증 입력에 대응시키는 과정으로 시작한다. 계약의 대기기간과 환경의 비워진 시점을 구분하고, 두 대기 규칙이 후보의 허용 여부를 어떻게 바꾸는지 기존 Table 3으로 보여준다.
2. Table 3의 점수와 reference 열을 유지하는 경우, 이를 읽는 데 필요한 합성 점수와 최고 점수 허용 후보의 정의만 간단히 남긴다. 독립적인 선택 목표와 제약 만족을 구분하는 개념 설명은 유지하되 학습 절차의 상세 내용으로 확장하지 않는다. R13의 문단 초안은 이 방향으로 정리했다.
3. `Candidate labels rotate...`와 고정 문자 답변 단서를 줄이는 이유는 V의 데이터 구성 설명으로 옮긴다. 그곳에서 행동 후보 선택 VLM인 Qwen3-VL-2B-Instruct의 역할과 입력·출력, 정답 구성 방식을 소개한 뒤 설명한다. 같은 라벨 회전 설명을 방법 절과 실험 절에 반복하지 않는다.
4. `Constraints and learning references are managed separately` 문단의 독립 정답 계산 상세 내용은 IV.E의 학습 입력 연결 설명이나 V의 참조 정답 설명에 통합한다. IV.C에서는 제약을 명세한 것만으로 실제 장면의 정답이 확정되는 것은 아니라는 범위 구분만 짧게 유지한다. R09·R12의 입력 출처와 검토 범위 설명을 학습 정답 생성 결과로 혼동하지 않도록 한다.
5. `What Is Extracted, From Where, and Where It Is Placed`의 출처 → 명세 필드 대응은 IV.C에 유지한다. 모델 입력의 정확한 문자열 결합, 정답 라벨 및 학습 기록의 세부 설명은 IV.E의 `Combining CNL with Learning Inputs`로 통합하여 Table 6과 연결한다.
6. IV.C의 도출 예제 → IV.D의 성질·질의 검사 → IV.E의 CNL 및 CoC 결합 → V의 학습·평가 설정 순서가 이어지도록 짧은 연결 문장을 넣는다. 이미 정의한 개념은 참조하고 각 단계에서 필요한 정보만 설명한다.

시간 예제 첫머리와 다음 절로의 연결 문구 취지는 다음과 같다. 검토 당시 제안이다.

> This example illustrates how CoC, a supplied clearance observation, and an explicit waiting rule are mapped to EBLC fields and verification inputs. It then compares the candidate permissions implied by two waiting requirements.

> The following subsection checks these permission conditions through logical queries. The subsequent CNL-generation subsection shows how the checked restriction is expressed and appended to the original CoC; learning-data construction and model training are described in the experimental setup.

이는 원고의 배치·연결을 정리하는 수정이며 실험이나 구현을 변경하지 않는다. 후보 표, 점수·reference 정의 및 검증 성질 설명은 R03·R09·R10·R13과 함께 일관되게 반영한다.

## R15 Table 4의 출처·필드 대응과 후속 문단 연결

- [x] 반영·검증 완료 (2026-10-05)

위치는 `What Is Extracted, From Where, and Where It Is Placed`의 Table 4 뒤 두 문단이다. 첫 문단은 규칙의 수치 제한이 계약 필드로, 후보 측정값이 질의 입력으로 들어간다는 표의 대응 관계를 구체화한다. 따라서 표를 명시적으로 참조한 뒤 설명을 시작한다. 표에 label을 부여하고 다음 취지의 문구를 사용한다.

> Following the source-to-field mapping in Table 4, numerical bounds are taken from supplied rule fields, while candidate measurements are bound separately in verification queries.

뒤에서는 `field`는 제한할 후보 속성, `op`는 비교 연산, `unit`은 외부 단위, `ticks`는 정수로 스케일 변환한 제한값임을 간단히 설명한다. `scale = 1000`은 모든 값을 시간 밀리초로 바꾸는 뜻이 아니라, 해당 외부 단위의 수치를 1000배 정수 표현으로 변환한다는 뜻이다. 규칙의 제한값과 검사할 후보의 측정값이 서로 다른 입력이라는 구분을 유지한다. 실제 장면에서는 R12의 근거·적용 여부 확인이 필요하고, 합성 과제의 학습 성능이 실제 영상에서 제약을 정확히 추출했다는 증거가 되지는 않는다는 범위를 연결한다.

두 번째 문단은 Table 4의 원래 CoC 보존 및 명세 출처 추적과 연결되지만, 상세 내용은 생성 CNL의 모델 입력 삽입 위치와 별도 기록 관리에 해당한다. R14에 따라 IV.E의 `Combining CNL with Learning Inputs`로 통합하여 Table 6과 연결한다. IV.C에서는 명세와 입력의 출처·필드 대응을 설명하고, 생성된 문장의 최종 위치는 후속 CNL 절에서 다룬다는 연결만 남긴다.

통합된 CNL 설명에서는 원래 CoC에 제약 문장을 붙인 뒤 후보 설명과 선택 지시를 제시한다는 순서를 명시한다. EBLC·출처·검증 결과·정답 라벨은 별도 기록으로 보존하고, 모델 입력에는 정답 라벨이나 SAT·UNSAT 결과를 힌트로 넣지 않는다는 구분을 유지한다. R09의 학습 정답 구성 설명과도 맞춘다.

## R16 시간 계약의 논리 변환 문단의 목적을 먼저 명시

- [x] 반영·검증 완료 (2026-10-05)

위치는 `Binding Checks and Core Lowering`의 `Temporal contracts lower to Core declarations`로 시작하는 문단이다. 변수 선언과 내부 설정을 나열하기 전에, EBLC 시간 계약을 SMT 솔버가 검사할 수 있는 논리 표현으로 변환하는 과정을 설명한다는 목적을 첫 문장에서 밝힌다.

문단 시작에 다음 문장을 넣고 기존 변수·상수 대응 및 자료형 검사 설명을 이어간다.

> To enable SMT checking, EBLC temporal contracts are first translated into Core, an intermediate representation of typed variables and logical clauses.

이 첫 문장으로 Core의 역할을 소개하므로 뒤의 `Core is an intermediate representation` 문장은 자료형 검사 후 SMT 표현으로 변환한다는 설명에 통합하여 반복을 줄인다. Boolean `enters`, 정수 `clear_ms`·`entry_ms`, 계약의 정수 상수 `release_clear_ms`를 구분하고, 질의별 값 대입은 R05의 설명과 맞춘다. 밀리초 정수 표현과 단위 표시 `1`, 시간 불변 변수·초기 조건 적용, `horizon = 2`의 모델 범위 의미는 이 변환 설명 뒤에 배치한다. 설정값을 실제 2초의 주행 궤적 검사로 읽히게 하지 않는다.

## R17 후보 표와 시간 경계 그림의 중복 축소

- [x] 반영·검증 완료 (2026-10-05)

검토 대상은 현재 Table 3과 Figure 4이다. Table 3은 후보 A–D의 진입 시점·합성 점수·두 대기 규칙의 허용 여부 및 reference를 보여준다. Figure 4는 같은 해소 시점과 대기 규칙의 진입 허용 경계를 시간축으로 보여준다. 표현 방식과 상세 정보는 다르지만, 두 규칙에서 11.5초·12.5초부터 진입이 허용된다는 핵심 설명이 겹친다. 기존 Table 5에는 11.499초·11.500초·11.501초 경계 질의와 기대 판정도 있으므로 경계값 포함을 설명하기 위해 그림을 별도로 반복할 필요가 작다.

일괄 수정 시의 편집 제안은 Table 3과 Table 5를 유지하고 Figure 4를 본문에서 생략하는 것이다. Table 3은 구성한 후보와 조건별 허용 결과를, Table 5는 검사할 성질·질의·기대 판정을 보여주는 역할로 구분한다. Table 5의 현재 일반적인 캡션은 `Properties, verification queries, and expected verdicts` 등으로 구체화한다. R03의 Table 3 캡션 구분과 함께 반영한다.

구역 해소 11.0초에 대기기간을 더하여 각각 11.5초·12.5초의 허용 경계를 얻으며 경계값을 포함한다는 설명은 본문과 기존 질의 표에 유지한다. 진입 보류 D는 시간축 위의 진입 시점이 아니라는 의미도 후보 표의 `No entry`와 해설에 유지한다. 명세 해석을 계산한 사례와 실제 모델 예측 결과를 구분하는 R13의 설명은 유지한다.

이 방향에 맞춰 R10의 Figure 4 연결 제안은 Table 3 → Table 5 연결로 정리했다. 원고 반영 시 후속 그림 번호·본문 참조·배치 및 산출물의 변경 허용 검사도 동기화한다. 기존 실행 기록이나 역사적 그림 파일을 삭제하는 작업은 포함하지 않는다.

## R18 방법론을 제약 추출·명세·검증 단계로 재구성

- [x] 반영·검증 완료 (2026-10-05)

범위는 IV `Proposed Method`의 구성이다. 현재는 EBLC 요소·의미를 먼저 상세히 설명한 뒤 제약 도출 절에서 다시 명세 절차를 설명하며, 후보 검증·학습 정답·CNL 삽입도 도중에 섞여 나온다. 사용자의 요청에 따라 목적별 단계를 분리하고 각 단계의 입력·처리·산출물을 밝힌다. 기존 절의 단순 제목 변경에 그치지 않고 해당 목적에 맞게 문단을 재배치한다.

제안하는 IV의 순서는 다음과 같다. 아래 절 번호는 개편안이며 원고 반영 시 제목·label·본문 참조를 함께 조정한다.

| 단계와 제안 절 | 입력과 처리 | 산출물 및 설명 범위 |
|---|---|---|
| A. Overview and Scope | CoC·관찰·제공된 규칙·가정 및 전체 흐름 소개 | 추출 → EBLC 명세 → 논리 검증 → CNL·CoC 결합의 관계와 지원 범위 |
| B. Extracting Constraint Candidates and Binding Evidence | CoC에서 행동 관련 후보를 식별하고 관찰·규칙·가정의 역할 및 출처를 구분; 사람 확인과 미확정 정보 관리 | 근거에 연결된 제약 후보 및 명세에 필요한 입력; 현재 제공된 합성 입력과 실제 장면 검토를 구분 |
| C. Specifying Behavioral Constraints in EBLC | 대상·조건·행동 제한·유지·해제·기간·가정·근거를 지원 필드에 명세하고 의미를 정의 | EBLC 계약, 시간·정성 프로파일의 해석 규칙, 별도로 필요한 환경·후보 입력 |
| D. Verifying EBLC Specifications | 구조·자료형·단위 검사, Core·SMT 변환, 검사할 성질과 질의·예상 결과 및 실행 결과 설명 | 주어진 모델과 가정 아래 일관성·제한 적용·경계·진입 가능성의 판정과 검사 범위 |
| E. Generating CNL and Augmenting CoC | 검사된 계약 필드를 문장으로 표현하고 원래 CoC에 추가 | 실제 CoC+CNL 예제, 대응 범위, 모델 입력과 별도 검증·정답 기록의 구분 |
| F. Task-to-Field-to-Verdict Summary | 앞 단계의 정의를 여러 지원 과제에 대응 | 기존 과제 → 필드 → 논리식 → CNL → 판정 표를 요약으로 유지; 단계 설명을 다시 반복하지 않음 |

추출 단계에서는 제약 후보를 찾는 일과 그것을 확정된 계약으로 만드는 일을 구분한다. 수치와 해제 조건을 CoC나 영상에서 임의로 도출하지 않는다. 실제 장면의 사람 확인 항목은 R12에 따라 이 단계에서 설명하며, 완전 자동 추출의 구현·정확성을 입증한 것으로 쓰지 않는다. 현재 Table 4의 출처·내용·목적지 대응은 단계 B와 C를 연결하는 표로 배치한다.

명세 단계에서는 현재 `Formal Specification with EBLC`의 요소·계약 해석·시간 및 정성 의미와, 현재 `Specification Procedure`의 필드 구성 부분을 통합한다. 현재 Code Box 1·2는 각각 시간 계약과 정성 상태 갱신 규칙으로 소개한다. 이전 상태에 따른 활성화·유지·해제는 명세의 해석 의미이며, 이것을 검사하는 질의는 단계 D에서 별도로 설명한다. Table 3은 명세된 규칙에 따른 후보 허용 여부를 보여주는 시간 예제로 사용하고 점수·reference 설명은 필요한 최소 정의로 유지한다.

검증 단계에서는 무엇을 검사하는지 먼저 밝힌 뒤 구현 설정과 솔버 표현을 설명한다. 특히 CoC에 추가할 제약의 허용·불허 범위가 의도한 규칙과 일치하는지 확인한다는 목적을 R09·R10과 연결한다. 너무 이른 진입은 배제되어야 하고, 요구 대기를 마친 진입은 가능해야 한다. 기본 SAT만으로는 진입 보류 사례만 존재할 수도 있으므로 해제 후 진입 가능성을 따로 확인한다.

Safety와 liveness의 범위는 명확히 구분한다. 조기 진입 반례를 배제하는 질의는 인코딩된 모델 안에서 제한 위반을 금지하는 safety 성질을 검사한다. 해제 후 진입 질의의 SAT는 적절한 진입 값이 존재한다는 진행 가능성·feasibility 검사이다. 진입 보류가 허용되므로 언젠가 반드시 진입한다는 liveness는 보장하지 않는다. 또한 원래 CoC 전체를 논리화하거나 CoC+CNL 문장 전체의 의미·일관성을 증명한 검사로 확대하지 않는다. 실제 관찰의 진실성, 제공된 대기 규칙의 실차 안전성, 학습 VLM의 선택 성능은 별도 근거가 필요하다.

검증 목적과 범위를 소개할 영어 문구의 취지는 다음과 같다. 검토 당시 제안이며 기존 성질 설명과 통합한다.

> Before expressing a contract as CNL for CoC augmentation, we check whether its executable representation excludes prohibited candidates while retaining intended permissions. The early-entry query checks a safety property within the encoded model. SAT queries at and after release establish entry feasibility, rather than a liveness guarantee that entry eventually occurs; deferral remains permitted. These checks concern the contract representation and its supplied inputs, not a formal proof of the original CoC or the combined natural-language text.

학습 모델·LoRA 설정·정답 계산·라벨 회전·성능 측정은 V `Experimental Setup`에 모은다. E에서는 제약이 어느 문장으로 생성되고 CoC에 어떻게 결합되는지와 모델에 보이는 정보만 설명한다. R14의 국소 배치 수정은 이 전체 단계 구성에 맞춰 적용하며, R01–R17에 기록한 위치·표·그림 번호는 개편 전의 식별 기준으로 취급한다. 반영 후에는 제목·label 기준의 참조와 각 항목의 완료 상태를 갱신한다. 실험·코드를 변경하거나 새로운 추출·검증 능력을 추가하는 작업은 포함하지 않는다.

## 1차 일괄 반영 결과 — 2026-10-05

영문 방법론 Markdown, 영문 실험 설정 Markdown, `main.tex`, 현재 영문 산출물 TeX 및 PDF를 동기화했다. 방법론은 개요 → 제약 후보 추출·근거 연결 → EBLC 명세 → 논리 검증 → CNL·CoC 결합 → 과제별 요약 순서로 재구성했다. 학습 정답 구성과 라벨 회전은 실험 설정에 배치했다.

검증 절은 인코딩된 모델 안의 조기 진입 제한 성질과 해제 후 진입 가능성을 구분하며, liveness·CoC 전체의 형식적 일관성·실차 안전성을 검증한 것으로 확대하지 않는다. 계약 필드와 질의 입력, 심볼·단위, 이전 활성 상태와 현재 근거, 사람 확인 항목 및 합성 점수와 reference의 의미를 명시했다. S1–S5 내부 코드 링크는 역할·버전·실행 기록을 소개하는 설명과 집필 원문의 구현 근거 목록으로 정리했다. 공개 코드·데이터 제공 위치는 제출 준비에서 확정해야 하는 항목으로 남아 있다.

| 검토 당시 식별자 | 개편 후 식별자 | 역할 |
|---|---|---|
| Table 2 | Table 3 | EBLC 요소 |
| Table 3 | Table 4 | 시간 후보의 허용 여부·합성 점수·reference |
| Table 4 | Table 2 | 출처와 명세 필드 대응 |
| Table 5 | Table 5 | 검증 성질·질의·기대 판정 |
| Table 6 | Table 6 | 원래 CoC와 추가 CNL |
| Figure 2 | Figure 3 | 정성 생애주기 |
| Figure 3 | Figure 2 | 근거와 필드 대응 |
| Figure 4 | 본문에서 생략 | 시간 경계 중복 설명 |
| Figure 5 | Figure 4 | 명세와 CNL 대응 |
| Figure 6–8 | Figure 5–7 | 기존 실험 결과 그림 |

PDF는 두 차례 컴파일하여 18쪽을 유지했다. 미해결 참조·인용·누락 문자와 새 본문 넘침은 없었으며, 기존 첫 페이지 overfull 경고 2건과 템플릿 폰트·색상 경고는 남아 있다. 수정된 본문·표·코드·최종 참고문헌 페이지를 시각 확인했다. 이전 스냅샷·한글 원문·실험 및 실행 기록 등 보존 대상 149개 파일의 해시와 기존 결과 절 내용이 유지되었다. 파일명 검사는 수정 파일에서 문제가 없었으며 범위 밖 기존 10건을 보고했다.

[현재 영문 PDF](ieee-access-manuscript-en.pdf)와 [검증 기록](RESULT.json)을 확인할 수 있다.

## 1차 일괄 반영 확인사항

- [x] R01–R18을 영문 방법론 Markdown과 `main.tex`에 함께 반영한다.
- [x] 현재 영문 산출물 TeX와 PDF를 동기화하고, 변경된 본문·캡션에 맞춰 빌드 검사와 검증 기록을 갱신한다.
- [x] 표 번호와 참조가 일치하고, 보행자 예제의 반복이 줄었으며, 허용성과 선택 목표의 수학적 설명이 유지되는지 확인한다.
- [x] 시간 제약식의 심볼이 첫 사용 전에 정의되고, EBLC 계약 필드·Core 변수·질의별 입력의 구분이 실제 구현과 일치하는지 확인한다.
- [x] 정성 프로파일의 설명이 Code Box 2의 `on`, `clear`, `previous_active` 및 각 줄과 일치하고, 상태 갱신과 진입 허용을 구분하면서 같은 규칙·예제를 반복하지 않는지 확인한다.
- [x] S1–S5의 불명확한 내부 코드 라벨과 로컬 절대 경로를 정리하고, 본문 설명과 논문용 구현 출처의 추적 가능성을 함께 유지하는지 확인한다.
- [x] 주요 학습·행동 평가, 별도 정성 명세 검사, 실제 관찰 이력 검증의 범위를 구분하고 이전 상태의 사용 여부를 각 경로에 맞게 설명하는지 확인한다.
- [x] 프로파일 구조 검사·행동 의미 검사·학습 정답 생성을 구분하고, 허용·불허 후보를 모두 검사하는 목적과 허용 후보만 정답으로 제공하는 방식을 실제 구현에 맞게 설명하는지 확인한다.
- [x] 기존 검증 표와 Code Box 3을 재사용하여 검증 성질·입력 조건·기대 판정·오류 예를 연결하고, 구체적인 후보 검사와 기호적 반례 검색의 범위를 구분하는지 확인한다. 성질 설명 문단이 Table 3의 허용 조건을 Table 5의 질의로 연결하고, 논리적 만족 대입과 학습 VLM의 의미를 혼동하지 않는지 확인한다.
- [x] 명세 구성 문단의 첫 문장에서 CoC·관찰·제공된 규칙으로 EBLC 명세를 구성하는 목적이 명시되는지 확인한다.
- [x] 명세 구성 입력의 출처, 계약의 규칙 매개변수와 질의별 환경·후보 입력, 자동화와 실제 장면의 사람 확인 범위를 구분하고 S3·S4를 논문용 출처 체계에 맞게 정리하는지 확인한다. 사람의 대상·구역·사건·시점·근거 채택·규칙·가정·초기 상태 확인과 학습 자료 채택 검토를 구체화하고, 검토 필요와 완료 상태를 구분한다.
- [x] 시간 예제의 후보 A–D가 사용 전에 소개되고, 해설 문단이 후보 표 참조로 시작하며 라벨별 행동 설명이 연결되는지 확인한다. 합성 점수의 고정 배정과 허용 집합 내 최대 점수 선택, 라벨 회전의 의미가 실제 구현과 일치하고 `reference`가 학습·평가의 기준 정답으로 정의되는지 확인한다.
- [x] 제약 도출 → 논리 검증 → CNL·CoC 결합 → 학습·평가 설정의 흐름이 이어지고, 라벨 회전과 학습 정답 구성의 상세 설명이 해당 절에 배치되어 방법 예제의 흐름을 끊지 않는지 확인한다.
- [x] Table 4를 참조하여 규칙 제한값·후보 측정값의 대응과 정수 스케일을 설명하고, CNL 삽입·기록 관리의 상세 설명을 Table 6의 학습 입력 연결과 통합하는지 확인한다.
- [x] 시간 계약의 Core·SMT 변환 문단이 목적과 Core의 역할을 먼저 밝히고, 변수 선언·자료형 검사·단위·모델 범위 설명으로 이어지는지 확인한다.
- [x] Table 3·Table 5의 역할을 구분하고 Figure 4 중복을 축소하는 편집 제안에 맞춰 그림 번호·참조·배치 및 산출물 검증 기록을 정리하는지 확인한다.
- [x] 방법론이 추출·명세·검증·CNL 결합 순서로 구성되고 각 단계의 입력·산출물과 범위가 명확한지 확인한다. 검증된 제한 성질, 진입 가능성, 보장하지 않는 liveness를 구분하고 학습 설정이 해당 실험 절에 모였는지 확인한다.
- [x] PDF의 페이지 수·표 배치·미해결 참조를 확인하고, 검증을 마친 항목만 완료로 표시한다.
## R19. Lifecycle 검사 설명을 쉬운 영어로 변경

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.D `Lifecycle Checks and Their Scope` 첫 문단.
- 사용자 승인 문구를 세 문단으로 반영했다. 검사 목적 → 초기·이전 활성 상태와 현재 근거 → 유지·해제·재활성화 규칙 → UNKNOWN에서 비활성 상태를 요구하면 UNSAT가 되는 예의 순서로 설명한다.
- 영문 방법론 Markdown, `main.tex`, 현재 영문 TeX·PDF를 동기화했다. 실제 영상 이력의 정확성을 입증하는 검사가 아니라는 범위 설명을 유지했다.
- 두 차례 컴파일 후 18쪽을 유지하고 PDF 11쪽의 수정 문단을 시각 확인했다. 미해결 참조·누락 문자·새 본문 넘침이 없으며, 해당 문단 외 통합 원고 내용과 보존 대상 149개 파일이 유지되었다. 파일명 검사는 수정 파일에서 문제가 없으며 범위 밖 기존 10건을 보고했다.

## R20. VS Code Build LaTeX의 latexmk 실행 오류 수정

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 오류: LaTeX Workshop 로그에서 `spawn latexmk ENOENT` 확인. 기본 빌드 명령인 `latexmk`가 환경에 없어서 컴파일 시작 전에 실패했다.
- 수정: 현재 영문 TeX와 `main.tex` 첫 줄에 `% !TeX program = pdflatex`를 지정한다. 설치된 LaTeX Workshop 10.19.0의 magic-comment 처리와 기본 활성 설정을 확인했으며, 해당 원고의 Build LaTeX가 설치된 `pdflatex`를 호출하게 한다.
- 사용자가 추가한 두 개의 `%` 주석 줄을 보존하고 `main.tex`에 동기화했다.

- 검증: 실제 LaTeX Workshop 로그에서 `Found TeX program by magic comment: pdflatex` 및 `Successfully built`를 확인했다. 검증용 두 차례 컴파일도 통과했고 PDF는 18쪽이다. 빌드 스크립트는 내용이 같은 TeX를 다시 쓰지 않아 불필요한 편집기 자동 빌드를 유발하지 않게 했다. 보존 대상 149개 파일과 사용자 수정은 유지했다.

## R21. CNL 문장 해설을 Figure 4와 명시적으로 연결

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.E.1 `Generating Sentences from Verified Specifications`의 `The first sentence identifies the zone and occupancy restriction`으로 시작하는 문단과 바로 뒤 Figure 4 (`fig:cnl-map`).
- 문제: 문단이 첫 번째·두 번째 문장의 역할을 설명하지만, Figure 4가 EBLC 명세 요소와 두 CNL 문장의 대응을 보여준다는 점을 먼저 밝히지 않는다.
- 수정: 문단 첫 문장에서 `Figure~\ref{fig:cnl-map}`를 참조하고, 그림에 제시된 두 CNL 문장을 설명하는 문단임을 명시한다. 첫 문장은 구역·점유 중 진입 금지, 둘째 문장은 해제 조건·요구 대기 시간을 표현한다는 순서로 설명한다. 그림 번호를 직접 고정하지 않는다.
- 유지할 내용: `at least`는 경계값을 포함하는 비교이고, `only after`는 진입의 필요조건이다. 진입을 강제하는 표현으로 해석하지 않는다. 500ms → 0.5s와 1500ms → 1.5s 변환, 지원 기간 및 단일 해제 시각·재점유 없음 가정의 범위를 유지한다.

문단 시작의 제안 문구:

> Figure~\ref{fig:cnl-map} shows how the EBLC specification maps to the two CNL sentences above. The first sentence identifies the zone and prohibits entry while it is occupied. The second states when this restriction can be released and how long the zone must remain clear.

일괄 반영 시 영문 방법론 Markdown, `main.tex`, 생성된 영문 TeX·PDF의 그림 참조와 문장 대응을 함께 확인한다. 데이터 생성·분할 소절과 규모 표를 추가하고 학습 설정을 별도 소절로 정리했다.

## R22. STOP 사례의 내부 장면 번호를 독자용 설명으로 변경

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.E.3 `Combining CNL with Learning Inputs`의 Table 6 해설 중 `in development scene #68`을 포함한 문장.
- 문제: `#68`은 내부 사례 식별자이며, 번호만으로는 독자가 장면이나 설명 목적을 이해하기 어렵다.
- 수정: 본문에서는 번호 대신 `in the worker's STOP-sign example`처럼 Table 6의 장면 내용을 설명하는 표현을 사용한다. 추적에 필요한 내부 식별자는 별도 근거 기록에서 유지한다.
- 유지할 의미: 원래 CoC의 빨간 신호 주장은 미확정이었고, 추가 제약은 별도로 확인한 작업자의 STOP 지시에 근거했다. 제약을 추가해도 원래 CoC의 모든 사실 주장이 검증되는 것은 아니라는 한계를 설명한다. STOP 사례를 주된 합성 학습 성능 실험에 포함한 것으로 표현하지 않는다.

제안 문구:

> Adding a constraint does not confirm every factual claim in the original CoC. In the worker's STOP-sign example, the original claim about a red light remained unconfirmed. The added constraint was based on a separately confirmed STOP instruction from the worker.

## R23. P0·P1·P2를 실험 입력 비교 조건으로 먼저 소개

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.E.3의 `P0 receives original CoC` 문장과 V `Experimental Setup`의 비교 조건 소개.
- 문제: 코드명만 갑자기 등장해 모델 이름인지, 처리 단계인지, 실험 조건인지 알기 어렵다. 현재 원고의 비교 조건 식별자는 P0·P1·P2이다.
- 수정: 식별자를 사용하기 전에, CoC에 제약을 추가하는 효과를 평가하기 위한 세 가지 모델 입력 조건임을 먼저 밝힌다. 첫 등장 시 P0 = 원래 CoC만, P1 = 원래 CoC + 기존 자연어 제약, P2 = 원래 CoC + EBLC에서 생성한 CNL로 정의한다.
- 흐름: 방법론에서는 CoC+CNL 입력 구성과 실험 비교의 연결을 짧게 소개하고, 상세 학습·평가 설정과 비교 조건 표는 V에서 설명한다. V에서도 정의보다 먼저 P1·P2를 사용하는 문장이 있는지 함께 확인하여 설명 순서를 맞춘다.
- 유지할 의미: P1·P2는 모두 제약을 추가하는 접근이며, 주된 기준 조건은 CoC만 제공하는 P0이다. 기준 정답, 원시 EBLC JSON, SAT/UNSAT를 입력의 정답 힌트로 제공하지 않는다.

제안 문구:

> To evaluate the effect of adding constraints to CoC, we compare three input conditions. P0 uses the original CoC alone. P1 adds the existing natural-language constraint, and P2 adds CNL generated from EBLC. Both P1 and P2 are compared primarily with P0. The experimental setup is described in Section V.

일괄 반영 시 절 참조는 LaTeX label을 사용하고, 조건 이름과 실제 비교 조건 표의 정의가 일치하는지 확인한다. R22·R23은 현재 수정 목록에만 기록하며 원고에는 반영하지 않는다.

## R24. Table 7 소개에서 내부 테스트 사례 번호 삭제

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.F `Task-to-Field-to-Verdict Summary`의 Table 7 (`tab:taskmap`) 소개 문단.
- 문제: `static scene 20000`, `stopping scene 20000`, `lane-change scene 20001`의 숫자는 내부 테스트 식별자이며, 과제와 EBLC 필드·논리식의 대응을 이해하는 데 필요하지 않다.
- 수정: 본문에서 해당 숫자를 삭제하고, 표가 보관된 테스트 계약의 구체적인 예를 이용해 여섯 과제의 명세·검증 대응을 보여준다는 목적을 먼저 설명한다. 내부 식별자는 재현을 위한 별도 실행·근거 기록에 유지한다.
- 유지할 의미: 시간 제약 행은 앞서 설명한 진입 시각 경계값 질의를 사용한다. 이 표는 구현된 계약 예를 보여주며, 여섯 과제를 각각 독립적으로 수집한 실제 도로 영상으로 입증한 것처럼 표현하지 않는다.

제안 문구:

> Table~\ref{tab:taskmap} shows how the six evaluated tasks are represented by supported contract fields and logical clauses. The examples come from archived test contracts, and the temporal row uses the boundary query described above. These are examples of the implemented specifications, rather than six independently collected road videos.

현재는 수정 목록에만 기록하며, 영문 방법론·통합 LaTeX·생성 원고의 반영은 다음 일괄 수정 때 수행한다.

## R25. Table 7의 필드 출처와 논리식 사용 단계를 설명

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.F의 Table 7 (`tab:taskmap`) 소개·해설과 `Constraint fields`, `Actual logical condition` 열.
- 문제: 필드와 논리식이 나열되지만, 필드가 어디에서 왔으며 논리식이 언제 어떤 입력과 함께 사용되는지 연결 설명이 부족하다. 시간 제약 행에는 계약 필드와 환경 입력이 같은 열에 섞여 있다.
- 수정: 표 앞에서 제공된 규칙 → EBLC 명세 필드 → Core·SMT 논리식 → 후보 입력을 연결한 검증 → SAT/UNSAT 판정의 흐름을 짧게 설명한다. 현재 합성 실험의 제한값은 제공된 규칙에서 가져오며 CoC나 영상에서 자동 추론한 값이 아님을 밝힌다. 기존 명세·검증 절을 참조하여 상세 설명의 반복을 줄인다.
- 구체적 예: 최대 속도 4.4 m/s 규칙을 `speed / le / m/s / 4400`으로 기록하고, `scale = 1000`에 따라 4400은 4.4 m/s를 뜻한다고 설명한다. 이 필드가 `q ⇒ v_hat ≤ 4400`으로 변환되며, `q`는 후보의 과제 완료 여부이고 `v_hat`는 같은 정수 스케일의 최대 속도이다. 과제를 완료하는 후보의 최대 속도 6.0 m/s는 UNSAT, 2.8 m/s는 SAT인 예와 연결한다.
- 검증 시점: 계약을 논리식으로 변환한 뒤, 후보별 측정값과 완료·진입 여부를 별도 입력으로 연결하여 `Phi_C ∧ B(a)`를 검사한다. 논리식은 후보 호환성 검사에 사용하고, 최고 진행 점수 선택과 기준 정답 계산은 별도 목적·규칙에 따른다는 구분을 유지한다. CNL은 같은 계약 필드에서 생성되며 솔버의 판정이나 정답을 문장에 넣는 것이 아님을 밝힌다.
- 표 정리: 시간 제약 행의 `release_clear_ms = 500`은 계약 필드이고 `clear_ms = 11000`은 환경의 해제 시각 입력이다. `Constraint fields` 열에는 계약 필드를 두고, 환경 값은 명확히 표시한 질의 입력 설명으로 옮기는 방향으로 정리한다. 다른 행도 규칙 제한값과 후보 측정값이 구분되는지 확인한다.

표 소개에 통합할 제안 문구:

> Table~\ref{tab:taskmap} follows the path from supplied rules to EBLC fields, logical conditions, and candidate judgments. The constraint fields record the rule limits. During verification, these fields are compiled into logical conditions, and each candidate's measurements and completion or entry flag are supplied separately. The solver then checks whether the candidate is compatible with the contract. The same contract fields are also used to generate CNL.

R24의 표 소개 수정과 함께 통합한다. 영문 집필 원문·통합 TeX·현재 TeX/PDF에 일괄 반영하고 검증했다.
## R26. 감속도·저크 단위를 실제 위첨자로 표시

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: Table 7의 정지 과제 CNL 해설 및 같은 5.8 m/s^2 값을 설명하는 명세 문단.
- 수정: 문자로 출력되던 `5.8 m/s^2`와 `7.4 m/s^3`를 LaTeX 수식의 위첨자 단위로 표시한다. 값과 제약 의미는 유지한다.
- 영문 방법론 Markdown, `main.tex`, 현재 영문 TeX를 동기화했다. 사용자가 직접 변경한 STOP 예시 행의 제목도 보존·동기화했다. R21–R25는 일괄 수정 대기로 유지한다.

- 검증: 두 차례 컴파일 통과, PDF 18쪽 유지, 13쪽에서 m/s²·m/s³ 위첨자 출력을 시각 확인했다. 새 본문 넘침·미해결 참조·누락 문자가 없고 보존 대상 149개 파일은 유지되었다. 파일명 검사에서는 범위 밖 기존 10건만 보고했다.

## R27. 후보 검증과 학습 모델의 선택 평가를 쉬운 설명으로 분리

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.F의 `For a selected candidate a, the solver checks Phi_C and B(a)`로 시작하는 문단.
- 문제: 수식, SAT/UNSAT, 별도 과제 규칙, 진행 점수, 정확도·위반율, 두 구현의 비교 범위가 한 문단에 압축되어 있다. 솔버가 허용 여부를 검사하는 일과 학습 모델이 정답을 선택하는 일이 구분되도록 설명을 풀어 쓴다.
- 구성: 먼저 검사 목적을 밝히고 후보의 측정값·완료 여부(시간 과제에서는 진입 여부)를 계약 논리식에 연결한다는 뜻을 설명한다. 이어 별도 과제 규칙으로 허용 후보와 최대 진행 점수의 기준 정답을 계산하고, 학습 모델의 선택을 이 정답과 비교하는 단계를 설명한다. 마지막에 두 구현의 일치가 입증하는 범위를 짧게 밝힌다.
- 수식: `Phi_C ∧ B(a)`는 유지하되 평이한 설명 뒤에 두거나 별도 문장으로 정의한다. `Phi_C`는 변환된 계약 논리식, `B(a)`는 후보 입력을 지정한 조건임을 명시한다. `selected candidate`가 이미 학습 모델이 선택한 행동만 뜻하는 것으로 읽히지 않게 검사할 행동 후보라는 표현을 사용한다.
- 예: 충분히 기다린 뒤 진입하는 후보와 계속 기다리는 후보가 모두 SAT일 수 있다. 계속 기다리는 후보는 제약을 위반하지 않지만 진행 점수가 낮아 기준 정답과 다를 수 있다. SAT를 최적 행동이나 과제 완료 보장으로 해석하지 않는다.
- 평가·범위: 기준 정답과 같은 선택은 정답이고 허용되지 않는 후보 선택은 제약 위반이다. 허용되지만 기준 정답과 다른 후보는 정확도 오류이면서 제약 위반은 아닐 수 있다. 솔버 논리식과 별도 규칙 구현은 같은 제공 규칙·가정에 기반하므로 결과 일치는 구현의 대응을 확인하며, 규칙 자체의 실제 도로 안전성을 독립적으로 입증하지 않는다.

풀어 쓴 영어 문구의 제안:

> We first check whether an action candidate is allowed by the contract. The solver combines the compiled contract with the candidate's measurements and its completion or entry flag. In the query Phi_C ∧ B(a), Phi_C is the contract's logical representation and B(a) specifies these candidate inputs. SAT means that the candidate satisfies the encoded contract; UNSAT means that it does not.
>
> A separate implementation of the task rules also determines which candidates are allowed. Among them, it selects the candidate with the highest progress score as the reference answer. We compare the learned model's choice with this answer to measure accuracy. Choosing a prohibited candidate counts as a constraint violation.
>
> For example, both waiting and entering after the required delay may be allowed. Waiting can therefore return SAT but still be an incorrect answer if another allowed candidate has a higher progress score. Passing the constraint check and choosing the reference action are different requirements.
>
> We compare the solver results with the separate task-rule implementation to check that they agree. Both use the same supplied rules and assumptions. Their agreement checks the implementations; it does not independently establish safety on real roads.

일괄 반영 시 수식은 LaTeX 수식 표기를 사용한다. R25의 필드·논리식 소개 및 실험 절의 평가 정의와 연결하고 중복은 줄인다. 영문 집필 원문과 현재 TeX/PDF에 일괄 반영했다.

## R28. 저자 검토용 구현·실행 기록 목록을 본문에서 제거

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: IV.F.1 `Implementation and Query Records`의 두 문단.
- 문제: Python·JSON 파일명과 날짜가 붙은 내부 패키지 식별자, `author-review` 설명은 집필·검토용 기록 안내에 가깝다. 일반 독자의 방법 이해에 필요한 설명과 분리하고, 내부 작업 상태를 논문 본문에 나열하지 않는다.
- 수정: 해당 소절의 내부 파일·패키지 목록을 본문에서 제거한다. 역할·지원 버전·논리 검증의 범위 등 방법 이해에 필요한 정의는 앞의 명세·검증 절에 유지한다. 구현 파일과 실행 기록의 추적 정보는 기존 집필 근거 또는 보충자료의 재현 정보로 관리하며, 실제 기록 파일은 삭제하지 않는다.
- 재현성 안내: 기대·실제 판정과 SMT-LIB 질의가 보관된다는 필요한 설명은 검증 기록을 소개하는 기존 문장과 보충자료에 통합해 중복을 줄인다. 공개 코드·데이터 위치가 확정되면 해당 저장소·버전·자료의 범위를 Code/Data Availability에서 안내한다. 확정되지 않은 공개 주소나 공개 완료 상태를 만들지 않는다.
- 문맥 정리: 앞 문단과 Code Box 설명 등이 `implementation-records subsection`을 참조하는지 확인하고, 소절을 제거할 때 보충자료 또는 실제 제공되는 구현 근거로 참조를 함께 수정한다. `a public code and data availability location remains to be supplied for publication` 같은 제출 준비 상태 문장은 논문 본문에서 빼고 집필·제출 체크 항목에 남긴다.

R07의 구현 출처 추적 원칙은 별도 기록에서 유지하되, 논문 본문에는 독자가 이해할 수 있는 방법 설명과 필요한 공개·보충자료 참조를 사용한다. 내부 목록 소절과 연결 참조를 정리하고 집필 근거의 구현·질의 기록 링크는 유지했다.
## R29. 비교 조건 표의 label과 설명 문단 참조 추가

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: V.A의 `Comparison conditions and roles` 표와 앞의 소개 문단.
- 수정: 표 캡션 뒤에 `\label{tab:comparison-conditions}`를 추가하고, 문단 첫 문장에 `Table~\ref{tab:comparison-conditions}`를 사용하여 세 비교 조건과 평가 역할을 요약하는 표임을 밝힌다.
- 영문 실험 설정 Markdown의 Table E1 참조, `main.tex`, 현재 영문 TeX를 동기화했다. 기존 일괄 수정 대기 항목은 유지한다.

- 검증: 두 차례 컴파일 후 참조가 Table 8로 정상 해석되고 PDF는 18쪽을 유지했다. 미해결 참조·누락 문자·새 본문 넘침이 없으며 실험 결과 본문과 보존 대상 149개 파일은 유지되었다. 파일명 검사에서는 범위 밖 기존 10건만 보고했다.

## R30. 평가 데이터의 생성 절차·규모·분할을 본문에 설명

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: V `Experimental Setup`의 학습 설정 문단과 `Candidate References and Label Assignment`. 필요하면 데이터 구성 소절·표를 두어 학습 하이퍼파라미터와 분리한다.
- 문제: 학습 행 수와 일부 이미지 수만으로는 객관식 평가 데이터가 어떻게 만들어졌으며, 무엇을 얼마나 평가했는지 알기 어렵다. 보충자료 안내만으로 핵심 평가 설계를 대신하지 않는다.
- 용어: 사용자 요청의 검증·평가 데이터는 VLM의 validation/test 사례이다. EBLC 명세를 검사하는 SMT 질의 데이터와 구분하여 두 규모를 섞지 않는다.

실제 생성·실행 프로토콜에서 확인한 핵심 규모는 다음과 같다. 행 수는 각 P0·P1·P2 조건당 수이며, 별도 반복 난수 시드 3개를 데이터 규모에 곱해 독립 사례 수로 세지 않는다.

| 과제군 | 학습 행 | 검증(validation) 행 | 주 테스트 행 | 학습 / 검증 / 주 테스트 고유 이미지 |
|---|---:|---:|---:|---|
| 시간 제약 | 960 | 240 | 240 | 40 / 10 / 10 |
| 정적 제약 | 576 | 별도 분할 없음 | 144 | 18 / 해당 없음 / 13 |
| 기동 제약 | 384 | 별도 분할 없음 | 96 | 2 / 해당 없음 / 2 |

정적 제약은 최대 속도·최소 장애물 간격·최소 진입 지연의 세 과제로 구성되며, 학습은 각 192행, 주 테스트는 각 48행이다. 기동 제약은 정지·차선 변경의 두 과제로 구성되며, 학습은 각 192행, 주 테스트는 각 48행이다. 정적·기동 실행 프로토콜에는 별도 validation 분할이 없고 고정 학습량의 마지막 체크포인트를 사용한다. 시간 과제의 validation 결과가 체크포인트 선택에 사용되었다고 추정하지 않는다.

본문에 설명할 생성 흐름:

1. 합성 환경·도식과 후보 행동 템플릿으로 장면 정보 및 후보 수치 요약을 구성한다. 실제 도로 영상에서 행동을 추출한 데이터로 표현하지 않는다.
2. 제공된 규칙의 제한값·대기 시간을 적용한다. 같은 장면과 후보에 다른 규칙을 적용하는 계약 쌍을 구성하여 정답 변화에 대한 반응을 평가한다.
3. 별도의 과제 규칙 계산으로 허용 후보와 최대 진행 점수의 기준 정답을 정한다. 금지 후보도 객관식 선택지에 남기되 학습 정답은 기준 후보이다. EBLC 판정은 대응 검사와 기록에 사용하며 정답 힌트로 입력하지 않는다.
4. 같은 사례에 P0·P1·P2 입력을 구성하고, 이미지·후보·정답·분할을 조건 간 공유한다. 데이터 레코드의 입력은 이미지 참조·CoC 또는 CoC+CNL·후보 설명·선택 지시이며, 기준 정답은 별도 평가·학습 목표이다.
5. 후보 문자 배정·규칙 값·후보 구성의 변형 방식과 분할 기준을 밝힌다. 행 수, 고유 이미지 수, 같은 장면을 공유하는 계약 쌍의 관계를 구분한다.

분할과 평가 범위:

- 시간 과제는 train/validation/test 사이의 동일 픽셀 이미지 중복이 0임을 생성 기록에서 확인했다. 같은 이미지로 여러 규칙·후보·문자 배정 사례가 만들어지므로 행 수를 고유 장면 수로 해석하지 않는다.
- 정적 주 테스트의 고유 이미지 13개는 모두 학습 이미지와 겹치며, 기동 과제는 동일한 두 도식을 반복 사용한다. 모든 과제에 이미지가 분리되었다고 쓰지 않는다. 새로운 수치 조건 평가와 새로운 영상 장면 일반화를 구분한다.
- 시간 과제의 validation/test/paraphrase/unseen-duration은 각각 240행이다. 정적 과제의 test/paraphrase/unseen은 각각 144행이고, 기동 과제의 test/paraphrase/unseen/hard는 각각 96행이다. 문장 변형 평가가 주 테스트 장면을 재사용한다는 점을 밝혀 이들을 모두 독립 사례로 합산하지 않는다.
- 공개 가능한 생성 코드·분할 목록·데이터 스키마·정답 계산 근거를 보충자료와 Code/Data Availability로 연결한다. 본문에는 내부 run ID나 worktree 경로 대신 독자가 이해할 수 있는 생성 방식과 규모를 제시한다. 공개 여부와 위치는 확정된 사실만 기재한다.

확인 근거는 시간 과제의 생성 RESULT 및 평가 protocol, 정적·기동 과제의 protocol·inventory 기록이다. R23·R25·R27과 연결하여 조건 정의 → 데이터 생성·분할 → 학습 설정 → 평가 지표의 순서로 정리한다. 데이터 생성·분할 소절과 규모 표를 추가하고 학습 설정을 별도 소절로 정리했다.

## R31. 과제별 성능 소절 앞에 실험 목적과 평가 방식 소개

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: VI.A `Performance Across Behavioral Tasks`의 첫 문단 앞.
- 문제: `The six task rows correspond directly to Table~\ref{tab:taskmap}`로 바로 시작하여, 이 소절에서 무엇을 평가하는지 알기 전에 표의 행과 논리 검사 연결부터 제시한다.
- 수정: 먼저 여섯 합성 과제에서 CoC에 제약을 추가했을 때 행동 후보 선택 정확도와 제약 위반율이 어떻게 달라지는지 평가하는 실험임을 짧게 소개한다. 비교 대상은 앞에서 정의한 P0·P1·P2이며, 각 테스트 사례에서 VLM이 후보 하나를 선택하고 기준 정답·허용 규칙과 비교한다는 평가 방식을 밝힌다.
- 연결: 실험 목적·비교 조건·지표를 소개한 뒤, 여섯 과제가 Table 7의 계약 필드·논리 조건에 대응한다는 기존 설명으로 이어 간다. `six task rows`가 바로 뒤 주 성능 표(Table 9)의 행을 뜻한다는 점도 명시하고, 필요하면 그 표에 label을 부여해 참조한다.
- 범위: 학습과 평가 때 제약을 제공한 조건의 성능 비교이며, 동일 정보 아래 순수 학습 효과나 실제 도로 안전성의 인과적 증명으로 확대하지 않는다. 모델 예측 사례 수와 명세·질의 검사 수가 다르다는 설명은 별도 문장으로 간단히 연결한다.

소개 문단의 제안 문구:

> We evaluate whether adding behavioral constraints to CoC improves action selection across six synthetic tasks. We compare the three input conditions defined in Table~\ref{tab:comparison-conditions}: CoC alone (P0), CoC with the existing natural-language constraint (P1), and CoC with EBLC-derived CNL (P2). For each test example, the model selects an action candidate. We report how often its choice matches the reference action and how often it violates the supplied rule.

R23의 비교 조건 정의와 R27·R30의 평가·데이터 설명을 참조하여 상세 내용을 반복하지 않는다. 실험 소개와 모델 평가·SMT 보조 검사의 구분을 반영하고 표 참조를 확인했다.

## R32. 두 성능 해설 문단에 결과표·시드별 그림 참조 명시

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 대상: VI.A의 `P1 and P2 have higher accuracy and lower violation rates than P0` 문단과 `P2 does not exceed P1 under every seed and condition` 문단.
- 문제: 어느 결과표를 해설하는지 명시하지 않고 수치·상대 성능을 설명한다. 첫 문단은 주 결과표의 평균을 설명하지만 둘째 문단의 시드별 변동은 평균만 있는 표로 확인할 수 없다.
- 확인: 현재 주 결과표(Table 9, `Primary accuracy / violation rate, %, mean over three seeds`)와 바로 뒤 시드별 성능 그림(Figure 5)에는 LaTeX label이 없다.
- 수정: 주 결과표 캡션 뒤에 `\label{tab:primary-performance}`, 성능 그림 캡션 뒤에 `\label{fig:task-performance}`를 추가한다. 반영 시 기존 label과 충돌하지 않는지 확인한다.
- 첫 문단: `Table~\ref{tab:primary-performance}`를 앞에서 참조하고 표가 세 시드 평균의 정확도·위반율을 제시한다는 점을 밝힌다. 이어 P0 대비 향상 폭과 과제별 P1·P2 결과를 설명한다.
- 둘째 문단: 같은 결과표를 참조하여 평균 결과의 비교 범위를 밝히고, 개별 시드 결과에 관한 설명에는 `Figure~\ref{fig:task-performance}`를 함께 연결한다. 평균 결과만으로 모든 시드·조건에서 우월하다고 주장하지 않는다. 주 결과 외 평가 조건까지 언급한다면 해당 결과의 근거도 함께 확인한다.
- 근거 범위: compliant completion 100%·99.17%와 낮은 진행 점수 후보 선택이라는 오류 해설은 현재 정확도·위반율 표에 직접 표시되지 않는다. 이를 모두 표의 직접 관측값처럼 서술하지 않고 별도 후보별 평가 기록·보충자료의 해당 근거와 연결한다. 표의 반올림 수치를 단순 차감한 값과 기존 보고 개선 폭의 차이는 필요 시 반올림 전 원자료로 확인하며, 요청 없이 수치를 변경하지 않는다.

문단 시작의 제안 문구:

> Table~\ref{tab:primary-performance} reports mean accuracy and violation rates over three seeds. P1 and P2 have higher accuracy and lower violation rates than P0 for all six task types.
>
> The mean results in Table~\ref{tab:primary-performance} summarize the comparison with P0, while Figure~\ref{fig:task-performance} shows the individual-seed results. P2 does not outperform P1 in every seed and evaluation condition. We have not conducted a formal noninferiority test between P1 and P2.

R31의 실험 소개와 함께 목적 → 주 결과표 → 수치 해설 → 시드별 변동·비교 범위의 순서로 정리한다. 원고·label·PDF에 반영했으며, 주 결과표는 Table 10, 시드별 성능 그림은 Figure 5로 연결된다.


## R33. Table 9의 고유 이미지 수 열 삭제

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 사용자 요청에 따라 `tab:dataset-sizes`의 마지막 열인 `Distinct images: train / validation / test`를 삭제했다. 표에는 Family·Training rows·Validation rows·Primary-test rows를 남겼다.
- 표 소개 문장을 행 수 안내로 수정하고 영문 실험 Markdown·main.tex·현재 TeX/PDF를 동기화했다. 사용자의 편집기 주석을 보존했다.
- 이미지 재사용 및 합성 평가의 범위를 설명하는 기존 본문은 유지했다. 위 R30의 고유 이미지 수 표는 확인 근거의 이력이며 현재 논문 Table 9의 열 구성을 나타내지 않는다.
- 두 차례 컴파일 통과: Table 9, PDF 19쪽, 미해결 참조·누락 문자·새 본문 넘침 없음. 빌드 보존 대상 149개 파일의 해시는 불변이다. 추가 데이터 구성이나 평가 실행은 하지 않았다.


## R34. Table 9를 단일 컬럼으로 조판

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 마지막 열 삭제 후 네 열로 구성된 `tab:dataset-sizes`를 전폭 `table*`에서 한 단 `table`로 변경하고 열 너비를 `columnwidth` 기준으로 조정했다. 표 내용과 본문은 유지했다.
- 통합 main.tex와 현재 TeX/PDF를 동기화했다. 두 차례 컴파일과 PDF 15쪽 시각 확인 통과: Table 9는 왼쪽 한 단에 배치되며, 전체 PDF는 19쪽이다. 미해결 참조·누락 문자·새 본문 넘침이 없고 빌드 보존 대상 149개 파일의 해시가 유지되었다.


## R35. 실험 결과 B·C·D절에 평가 목적 소개 추가

- 상태: [x] 반영·검증 완료 (2026-10-05)
- VI.B: 같은 장면·후보에서 규칙이 바뀔 때 모델의 선택이 바뀌는지, 그리고 학습에서 사례와 제약을 올바르게 연결하는 것이 중요한지 평가한다고 소개했다.
- VI.C: EBLC·CNL 오류 검출과 정상 계약 수용, 조기 진입 배제와 해제 경계 이후 진입 허용을 검사한다고 소개했다.
- VI.D: 학습에 없던 수치·대기 시간에서 정확도와 위반율을 평가하며 표현·입력 변경 진단으로 결과의 범위를 확인한다고 소개했다.
- 각 절에 두 문장으로 된 짧은 소개를 추가했다. 이미 소개가 있는 VI.A와 기존 수치·표·결과 해설은 유지했다. 영문 실험 Markdown의 C·D·E절이 통합 원고 VI.B·C·D에 대응한다.
- 영문 집필 원문·통합 main.tex·현재 TeX/PDF 동기화, 두 차례 컴파일 통과, PDF 16쪽의 절별 소개 배치 확인. 전체 19쪽, 미해결 참조·누락 문자·새 본문 넘침 없음. 빌드 보존 대상 149개 파일의 해시 불변이다.


## R36. 실험 결과 소절의 도입 표현 다양화

- 상태: [x] 반영·검증 완료 (2026-10-05)
- VI.A의 `We evaluate`는 유지하고 VI.B·C·D의 첫 문장을 각각 `Changing the rule...`, `To assess specification quality...`, `Tests with numerical values...`로 바꾸었다. 평가 목적·검사 범위와 나머지 문장은 유지했다.
- 영문 실험 Markdown·통합 main.tex·현재 TeX/PDF를 동기화했다. 두 차례 컴파일 통과: 19쪽, 참조 해결, 빌드 보존 대상 149개 파일 해시 불변.


## R37. 실험 결과 해설과 표·그림·그래프 참조 연결

- 상태: [x] 반영·검증 완료 (2026-10-05)
- VI.A의 Table 10·Figure 5 참조는 유지했다.
- VI.B의 계약 쌍 정확도 해설은 Figure 6 왼쪽, 올바른 연결과 섞인 학습 연결의 정확도 해설은 Figure 6 오른쪽으로 연결했다. `fig:contract-linkage` label을 추가했다.
- VI.C의 오류 검출률 해설을 Table 11에 연결하고, 시간 경계 질의와 기대 UNSAT 해설을 Figure 7에 연결했다. `fig:smt-boundary` label을 추가했다.
- VI.D의 미학습 수치·시간 조건 성능을 Table 12에 연결했다. `tab:unseen-conditions` label을 추가하고 문장 변형 수치는 별도 문단의 Supplement S8로 안내하여 Table 12에 표시된 값과 혼동하지 않도록 했다.
- LaTeX 자동 참조와 영문 실험 Markdown의 로컬 Figure 7·8, Table E3·E4 안내를 동기화했다. 기존 수치·표·그래프는 유지했다. 두 차례 컴파일 통과: 19쪽, label 중복·미해결 참조·누락 문자·새 본문 넘침 없음. PDF 16·17쪽의 해설과 Figure 5·6 배치를 확인했고 빌드 보존 대상 149개 파일의 해시가 유지되었다.


## R38. 주 성능 결과의 표·그래프 중복 제거

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 같은 평균 정확도·위반율을 보여주는 Table 10과 이전 Figure 5 가운데 Table 10을 유지하고 주 과제 성능 그래프를 본문에서 삭제했다. 수치 비교가 가능한 표를 유지하며 시드별 변동과 추가 조건은 Supplement S2·S8로 안내했다.
- `fig:task-performance` figure 블록과 참조를 제거했다. 이전 Figure 6의 계약 연결 그래프는 현재 Figure 5, 이전 Figure 7의 SMT 경계 그림은 현재 Figure 6이다. Table 10·11·12의 번호는 유지되었다. 위 R32·R35·R37의 옛 그림 번호는 해당 시점의 이력이다.
- 영문 실험 Markdown의 로컬 그림 번호와 통합 TeX를 동기화했다. 원본 그림 자산·보충자료와 실험 기록은 보존했다. 본문의 표 내용·수치는 불변이다.
- 두 차례 컴파일과 PDF 17쪽 배치 확인 통과: 19쪽, 그림 6개·표 12개, 미해결 참조·누락 문자·새 본문 넘침 없음. 빌드 보존 대상 149개 파일의 해시 불변이다.


## R39. AI 집필 지원 고지 단순화

- 상태: [x] 반영·검증 완료 (2026-10-05)
- Acknowledgment의 지원 고지를 `OpenAI Codex assisted with writing and editing this manuscript. The authors are responsible for its content and references.`의 두 문장으로 줄였다. `r15` 인용을 유지하고 저자·소속·연구비·기존 발표 메타데이터의 최종 확인이라는 집필 관리 문구를 본문에서 제거했다. 최종 확인 항목은 기존 paper README에서 관리한다.
- 통합 main.tex와 현재 TeX/PDF를 동기화했다. 두 차례 컴파일 통과: 19쪽, 참조 해결, 빌드 보존 대상 149개 파일 해시 불변.


## R40. 참고문헌을 BibTeX 데이터베이스로 분리

- 상태: [x] 반영·검증 완료 (2026-10-05)
- 본문의 수동 thebibliography 목록 15개를 paper/references.bib로 옮겼다. 저자·제목·연도·학회/저널·페이지·URL을 해당 BibTeX 필드에 기록하고 r1–r15 키와 현재 인용 번호 1–15를 유지했다. 미확정 발표 정보는 확정하지 않았다.
- CTAN의 원본 IEEEtran.bst를 기존 템플릿 의존성 디렉터리에 보관하고 출처·해시·라이선스 보존을 README에 기록했다. 원본 대문자 파일명은 정확한 단일 경로의 명명 예외와 범위 검사로 관리했다.
- main.tex와 현재 영문 TeX를 bibliographystyle·bibliography 방식으로 전환했다. 빌드 순서는 pdflatex → bibtex → pdflatex → pdflatex이며 bib 파일 수정은 소스 해시 재승인 없이 재빌드할 수 있다. 데이터베이스와 스타일의 해시를 RUN_MANIFEST에 기록한다.
- 빌드 및 PDF 19쪽 참고문헌 확인 통과: 19쪽, 참고문헌 15개, BibTeX 경고 없음, 인용·참조 해결, 새 본문 넘침 없음. 빌드 보존 대상 149개 파일의 해시 불변이다. 파일명 검사는 범위 밖 기존 10건만 남았다.

## R41 외부 연구와의 차이 및 추론 프롬프트 보조 비교

- [x] 반영·검증 완료 (2026-10-07)

관련 연구에서 DriveLM·DriveVLM의 장면 추론·계획 과제와 GuardSynth의 제약 개발 인터페이스를 구분하고, nl2spec·NL2TL의 언어→논리 번역과 EBLC→검사→CNL→CoC 학습 입력 경로의 차이를 설명했다. II.E와 Table 2는 원본 CLI 1개 예제·번역 3회, 원본 노트북 11개 예제, DriveLM의 로컬 LLaMA-7B 가중치 미확보, 확인한 DriveVLM 공식 저장소의 추론 코드·가중치 부재를 기록한다. 이는 공통 과제 성능표가 아니며, 실행 확인을 원논문 전체 재현으로 기술하지 않았다.

V.A.4에서 과제·출력·측정 단위와 실행 자원 차이로 직접 비교가 어려운 이유, P0 체크포인트에 적용한 두 추론 프롬프트의 절차·입력·예산을 설명했다. VI.B는 기존 480개 평가 행×3시드×2방법의 2,880건 채점 결과를 Figure 5와 연결한다. 동일 입력의 추론 재사용, 짧은 후보 문자 출력과 추론 토큰 상한 도달, 제약 미제공 조건의 50% 정답률 상한을 명시했다. P1/P2와의 차이를 동일 정보 조건에서의 알고리즘 우월성으로 해석하지 않는다.

영문 관련 연구·실험 Markdown과 통합/활성 TeX를 동기화하고 Zero-shot CoT·Plan-and-Solve 참고문헌 두 건을 BibTeX에 추가했다. Figure 5는 원본 결과 JSON으로 글자 크기를 본문 폭에 맞춰 다시 그렸으며 원본 비교 PDF는 보존했다. 새 표에 따라 데이터 규모·주 성능·명세 검사표는 Table 10·11·12이고, 계약 연결·SMT 경계 그림은 Figure 6·7이다. 21쪽 PDF, 그림 7개·표 13개·참고문헌 17개이며, LaTeX/BibTeX 빌드와 참조 해결 및 4·5·16–18쪽 배치 확인을 완료했다.

서론·배경·방법론·논의·결론과 기존 수치 표를 보존했다. 외부 실행 확인 및 추론 비교 산출물 66개 파일 해시와 빌드 보호 대상 215개 파일의 해시는 불변이다. 새 학습·평가를 실행하지 않았으며, 기존 실험 결과를 본문에 반영했다.


## R42. 보충자료의 표현·강건성·이미지·검사 단계 평가를 본문에 반영

- [x] 반영·검증 완료 (2026-10-07)

V.A.5에 제약 표현 방식, 문장 변화·복합 조건, 이미지 개입, 오류 종류별 검사 절차와 규모를 추가했다. VI.D–G는 Table 12–15와 연결하여 기본 성능 외에 표현별 일반화, 불리한 문장 변화 결과, 시각 입력 의존성, 공유 근거 오류의 미탐을 함께 설명한다. 새 표 세 개와 상세화한 오류 표는 모두 단일 컬럼이다. 별도 진단의 원본 기준 정답 유지, 24개 행·세 의미 그룹, 합성 장면 재사용과 자료 중복 집계 금지를 명시했다.

원본 결과 JSON과 표의 정확도/위반율 42개 셀 및 오류 8개 유형을 대조했다. LaTeX/BibTeX 빌드·참조 해결과 PDF 16–22쪽 배치를 확인했다. 전체 22쪽, 그림 7개·표 16개·참고문헌 17개이며 새 본문 넘침은 없다. 빌드 보호 파일 332개, 추가 원본 기록 117개와 외부 비교 근거 66개 파일의 해시는 불변이다. 서론·관련 연구·배경·방법론·논의·결론, 기존 주 성능·데이터 규모·미학습 값 표와 supplementary PDF를 보존했다. 새 학습이나 평가 실행은 없다.

