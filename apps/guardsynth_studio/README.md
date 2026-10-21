# GuardSynth Studio

- owner_project: `guardsynth-coc`
- subproject: `guardsynth-studio-sequential-coc`
- 화면: 최소 다섯 단계. 기존 자료와 모델 원문, 작성자 수정, 승인 이력은 보존한다.

## 최소 사용 흐름

영상과 추출을 선택하고 시점을 고른다. 추출은 간격과 프레임 수로 구분한다.
왼쪽에서는 현재·과거 최대 7개 프레임과 해당 시점 이전 CAN을 탐색한다.
새 CoC·제약 생성에는 바로 이전·현재 최대 2프레임과 해당 범위의 CAN만 전송한다.
슬라이더·썸네일로 이동하고 가운데 경계를 끌어 영상 너비를 조절할 수 있다.

1. **CoC 생성**: VLM 제안 본문과 수정 문장을 비교한다. 관찰 대상·방향 관계·실제 행동과 미확인을 자동으로 채우고 접힌 상세 항목에서 수정한다.
2. **제약 생성**: 7개 종류의 제약에서 원인 대상과 행동 적용 영역, 활성·해제 및 선행/기대 후행 조건을 검토한다. 정의와 현재 관찰값은 구분한다.
3. **EBLC 생성**: 검토한 제약으로 EBLC Core를 생성한다. SMT 실행은 이 단계에서 하지 않는다.
4. **검증**: 저장된 EBLC Core로 바로 이전·현재 장면을 검사한다. 더 오래된 조건은 최대 64개 상태 요약으로 넘긴다. 반례의 원문·근거에서 수정 칸으로 이동한다.
5. **CNL 생성**: 검증 상태와 제약을 결정적 문장 형식으로 표시한다. 이전 장면에서 유지된 조건도 포함한다.

CoC·제약을 수정하지 않으면 수용 체크 후 ‘검토 완료 · 다음’을 누른다.
수정 내용은 IndexedDB outbox/CAS로 자동저장하며, 원문은 변경하지 않는다.
앞 단계가 바뀌면 EBLC·검증·CNL 결과는 무효화되어 다시 실행해야 한다.
VLM 호출은 CoC·제약 생성 버튼에서만 발생한다. 뒤 세 단계에는 추가 모델 호출이 없다.

첫 버전은 준비된 영상·추출을 사용한다. 업로드, 행동 적절성 평가, 수동 규칙/계약,
학습 split·export 옵션은 작업 화면에 표시하지 않는다. 과거 저장 기록과 API는 호환성을 위해 유지한다.
텍스트 검토는 작성자의 확인이며, 자유 문장과 정형 행동의 의미 일치를 자동 증명하지 않는다.
새 구조화 흐름은 논리 검증과 규칙/법적 출처 검토를 따로 표시한다. 빈 제약, 필요한 근거의 미확인, 미지원 항목은 논리 통과로 세지 않는다. 기존 단순 형식의 기록은 원래 검토 기준과 함께 보존한다.
모델 최초 생성 쌍의 검증 결과는 원문에 묶어 보존한다. 사람의 수정이 들어간 생성과 수정 후 최신 검증 결과를 구분한다. 이 통과율은 시각 인식 정확도나 규칙 완전성의 점수가 아니다.
결과는 장면의 진실성·법규 완전성·운전 안전성 또는 학습용 승인을 보증하지 않는다.

## 실행

저장소 루트의 등록 runtime(PyAV/Pillow/Z3)을 사용한다.

```bash
runtime/alpamayo/ar1_venv/bin/python -B -m apps.guardsynth_studio.run \
  --run-id studio-local-001 --init-auth --actor studio-reviewer
runtime/alpamayo/ar1_venv/bin/python -B -m apps.guardsynth_studio.run \
  --run-id studio-local-001 --port 0
```

실행 자료는 `projects/04-guardsynth-coc/artifacts/restricted/guardsynth-studio-001/<run-id>/`에 저장한다.
기존 run-id 재시작 시 기록·호출 수를 보존하고 로그인 세션만 초기화한다.

실제 모델은 비밀값 없는 `--provider-config` JSON과 `OPENAI_API_KEY` 환경변수가 필요하다.
설정은 `mode: OPENAI`, 명시적 `model`, `transmission_approved: true`, 승인 영상 SHA-256 목록
`video_sha256_allowlist`, `max_calls`, `max_output_tokens`, `timeout_s`를 포함한다.
영상/CAN 전송 승인과 누적 호출 한도는 서버가 확인한다. 설정 누락 시 생성은 비활성이다.
키는 설정 파일·브라우저·DB·로그에 저장하지 않는다. 실패/결과 불명 호출은 예약된 호출 수에 포함되며 자동 재시도하지 않는다.

## 검증

```bash
runtime/alpamayo/ar1_venv/bin/python -B -m unittest discover -s apps/guardsynth_studio/tests -t .
```

별도 loopback HTTP/Chromium 테스트에서 다섯 단계 버튼, 원문 수용, 수정 무효화,
중복 호출 방지와 영상 탐색을 확인한다. 합성 입력·테스트 모델을 사용하며 유료 호출은 하지 않는다.
CPU 작업은 별도 프로세스와 시간/메모리 제한으로 실행한다. 생성 결과는 입력 snapshot과
부모 작업에 결합되므로 그 사이 수정·재생성이 있으면 `STALE_RESULT`로 남는다.

[사용 안내](static/manual.html)
