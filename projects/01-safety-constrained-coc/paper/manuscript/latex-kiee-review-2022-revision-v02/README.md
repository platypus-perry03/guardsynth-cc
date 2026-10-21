# KIEE 심사 대응 수정본 V02

- 소유 프로젝트: `safety-constrained-coc`
- 기준 원고: `../latex-kiee-review-2022-revision-v01/`
- 수정 범위: 2차 심사의 세 추가 확인 사항만 반영

## 제출 파일

현재 편집본은 [publication-v05.hwp](publication-v05.hwp)이며,
[publication.hwp](publication.hwp)도 동일한 V05 내용이다. 저자의 요청에 따라
전체를 **1단**으로 바꿨다. 제목·저자명·본문·표·캡션의 기존 글꼴과 글자 크기를
유지하고, 이전 쪽/단 경계에서 생긴 줄 단위 문단을 문장과 문단 단위로 합쳤다.
줄 끝에서 잘못 끊긴 영어 단어 12곳을 복원했다. 문장 중간에 끼어 있던 그림·표
블록 8곳은 문장이 끝난 뒤에 놓았다. 본문은 한 구역으로 이어지며, 이전 PDF의
강제 쪽·단 이동은 제거했다.

내용 표 12개와 그림 7개, 수식 이미지 2개, 저자 사진은 모두 **글자처럼 취급**
하는 인라인 개체다. 국문·영문 캡션 38개는 왼쪽 맞춤이며, 표 위 캡션과 표,
그림 앵커와 뒤 캡션은 함께 이어지도록 설정했다. 셀의 줄 단위 문단도 합치고
필요한 행 높이를 확보했다. 그림의 기존 크기와 모든 이미지 바이너리는 유지했다.

[publication-hwp-v05.pdf](publication-hwp-v05.pdf)는 V05 HWP를 `hwp-cli`로 렌더링한
**17쪽 확인용 미리보기**다. [publication-hwp.pdf](publication-hwp.pdf)도 동일하다.
전 페이지를 검토했으며 빈 페이지가 없다. 이 환경에는 한컴 한글이 없어
실제 한컴 화면·재조판·쪽수는 직접 검증하지 못했다. 확인용 PDF와 구조 검사는
한컴 검증을 대신하지 않는다. 학회 업로드 규정은 **HWP**이며 PDF/HWPX로
대신 제출할 수 없다. [publication.pdf](publication.pdf)는 별도의 기존 2단
LaTeX 게재본이다. V02–V04 HWP와 V02 미리보기는 원래 파일명으로 보존했다.

단독·교신저자는 김진현(Jin Hyun Kim), `jin.kim@gnu.ac.kr`,
[ORCID 0000-0002-2308-1638](https://orcid.org/0000-0002-2308-1638)이다.
첫 페이지 초록·키워드 뒤에 소속·이메일·ORCID를 배치했다. 지정 사진
`sections/jin.jpg`의 원본 바이트를 포함했고, 영문 감사의 글·참고문헌·저자소개를
유지했다. 그림·표의 국문·영문 설명 및 번호도 유지했다.

현재 소속·직급은 [개인 홈페이지](https://jin-kim.net/)와
[연구실 소개](https://aix.gnu.ac.kr/teams/)에 따라 Department of AI Information
Engineering, Gyeongsang National University / Associate Professor로 정리했다.
학위·이전 경력의 연도는 저자가 제공한 약력을 유지했다. 학사 대학과 KAIST의
영문 명칭, `2015 20 2019` 등의 오탈자는 이전 게재본에서 수정했다.
학회가 입력하는 권·호·페이지·DOI·접수/수정/게재 일자는 기입하지 않았다.

규정 입력 `publication_reference.pdf`와 양식 `publication_template.hwp`는
저자가 제공한 원래 파일과 이름으로 보존했다. A4 용지·여백·조선일보명조 글꼴을
유지했으며, 이번 V05에서는 저자의 요청에 따라 양식의 2단 설정을 1단으로 바꿨다.
한컴에서 열 때는 포함된 `fonts/ChosunNm.ttf`의 조선일보명조 글꼴을 사용한다.

저장 후 재읽기에서 본문의 공백 이외 문자와 각 문자의 글꼴·크기 지정이 보존됨을
확인했다. 줄 끝의 불필요한 하이픈 12개만 제거했다. 원문 표 318개 셀을
대조해 불일치 0건을 확인했다. 독립 `pyhwp 0.1b15` 파서도 표 12개·셀 318개·이미지
10개를 읽었으며, 단 설정은 1단 하나뿐이다. 미리보기 글꼴 대체와 렌더러 보고 문제는
0건이었다. HWP 생성에는
[hwp-cli v1.3.1](https://github.com/STAIxBWLB/hwp-cli/releases/tag/v1.3.1)을 사용했다.

V05 입력·편집 기록·검사 결과·미리보기는
`projects/01-safety-constrained-coc/artifacts/intermediate/kiee-publication-hwp-005/single-column-2026-10-05-001/`에
기록했다. `document.json`은 그림·사진을 포함한 자체 완결 입력이며 다음으로
HWP를 재생성한다.

```bash
HWP_FONT_DIR=<원고 경로>/fonts hwp new --from document.json -o publication-v05.hwp --strict
```

[publication-source.zip](publication-source.zip)은 게재본 소스·글꼴·그림·사진과 V05
HWP 생성 입력을 저장소 경로 구조대로 묶은 독립 패키지다. LaTeX 빌드는 압축을
푼 뒤 이 원고 디렉터리에서 `make publication`을 실행한다. 이 명령은 별도의
2단 LaTeX PDF를 만들며 V05 HWP를 덮어쓰지 않는다.

다음 파일은 기존 **심사용** 제출물이다.

1. [main.pdf](main.pdf): 수정 표시 논문. 이번 수정만 파란색이며 1차 수정은 검정색이다.
2. [response-to-reviewer-1.pdf](response-to-reviewer-1.pdf): 기존 리뷰어 1 답변서.

본문의 실험 수치와 주장은 심사용 V02와 같다.

## 소스 및 빌드

`main.tex`, `sections/`, `kiee-review.sty`, `references.bib`는 V02의 독립 소스다.
`response-to-reviewer-1.tex`는 독립 답변서 소스다. 글꼴과 그림은 원본
`../latex-kiee-review-2022/`의 자산을 참조하므로 해당 디렉터리를 함께 유지한다.

```bash
make manuscript
make rebuttal
make publication
```

LuaLaTeX 및 BibTeX가 필요하다. 중간 빌드 파일은
`projects/01-safety-constrained-coc/artifacts/public/kiee-review-002/revision-2026-09-30-001/`에
생성하고, 제출용 PDF만 이 디렉터리에 복사한다. 답변서 쪽 번호는 V02 원고 기준이다.

`publication.tex`는 같은 본문을 게재용 모드로 읽고 `kiee-publication.sty`와
`sections/09-author-biography.tex`를 적용한다. 게재본 중간 파일은
`projects/01-safety-constrained-coc/artifacts/public/kiee-publication-001/publication-2026-10-01-001/`에
생성한다. 기본 `make`는 기존 심사용 원고와 답변서만 빌드한다.

`fonts/ChosunNm.ttf`는 HWP 양식의 ChosunM(조선일보명조)에 대응하는 공식
업데이트 배포본이다. [조선일보 공식 배포 페이지](https://event.chosun.com/100/100font.html)의
[ChosunNm.zip](https://fontdown.chosun.com/100/ChosunNm.zip)에서 2026-10-01
가져왔으며 원본 글꼴은 수정하지 않았다. 세부 배포 조건은
[fonts/README.md](fonts/README.md)에 기록했다.
