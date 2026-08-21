# 주간정책회의 브리핑

전북특별자치도교육청 [주간정책회의 게시판](https://www.jbe.go.kr/jbeducation/board/list.jbe?boardId=BBS_0000681&menuCd=DOM_000000507001000000&contentsSid=3249&cpath=%2Fjbeducation)에
새 회의 영상이 올라오면, 유튜브 자동생성 자막을 받아 회의록과 지시사항을 정리해 웹으로 공개합니다.

별도 DB나 서버가 없습니다. 수집 결과는 `data/` 아래 JSON으로 쌓이고, 화면(Vite + React)이 그 JSON을 읽습니다.
UI는 `k-edu-policy` 와 같은 KRDS 토큰·Pretendard·Tailwind 구성을 씁니다.

## 세 단계로 나눠 돌아갑니다

```
1단계 · 자막                    1.5단계 · 교정·화자           2단계 · 요약
게시판 → 신규 dataSid            문장 단위로 합치고            회의록 + 부서 목록
 → videoId                      10분씩 토막 내서 LLM          + 지난주 지시사항
 → yt-dlp (json3→vtt→API)        → 문맥 교정                   → LLM
 → 부서명 사전 후보정              → 화자 추정                    → 요약·안건·지시·처리결과
   ↓                              ↓                            ↓
data/transcripts/*.json      data/refined/*.json          data/meetings/*.json
```

각 단계가 **따로 저장되고 따로 다시 돌릴 수 있습니다.** 뒤 단계가 실패해도 앞 결과는 남습니다.
앞 단계가 실패하면 뒤 단계는 시도하지 않습니다 — 자막 없이 만든 요약은 의미가 없습니다.

```bash
python collector/fetch_transcripts.py --check   # 단계별 진행 상태를 표로 확인
python collector/fetch_transcripts.py --all     # 1단계만
python collector/refine.py --dry-run            # 1.5단계 비용을 미리 계산
python collector/refine.py --all                # 1.5단계만
python collector/run.py                         # 신규 회차를 끝까지
```

처리 여부는 `data/index.json` 으로 판단합니다. 회의 ID는 게시일의 ISO 주차(`2026-W34`)입니다.

### 2단계는 사람이 해도 된다 (권장)

`summarize.py` 는 LLM API로 요약을 만들지만, **대화 세션에서 사람(또는 Claude)이 회의록을 읽고
`data/meetings/<회차>.json` 을 직접 작성해도 결과는 같습니다.** 실제로 지금 들어 있는 4회차는
그렇게 만들었습니다.

이 방식의 장점:

- API 키·모델 버전·비용이 필요 없습니다. 모델이 단종되어 실패하는 일도 없습니다.
- 발행 전에 사람이 한 번 보게 되므로, 잘못된 부서 배정이 그대로 나가지 않습니다.
- 애매한 대목은 물어보고 정할 수 있습니다.

주 1회이므로 부담도 크지 않습니다. 자막 수집만 자동으로 돌려두고, 정리는 요청해서 받은 뒤
`git push` 하면 됩니다.

**작성할 때 반드시 지킬 것**: `directives`·`followups` 의 `quote` 는 회의록에 실제로 있는 문장을
그대로 넣고, 저장 전에 검증하세요. 지어낸 인용은 이 서비스의 신뢰를 통째로 무너뜨립니다.

```python
full = " ".join(c["text"] for c in refine.merge_cues(transcript["cues"]))
assert all(d["quote"] in full for d in meeting["directives"])
```

### 전달사항 hwpx 내려받기

대변인실이 회의 후 배포하는 '전달사항' 문서와 같은 모양의 hwpx 를 만들어 줍니다.

```bash
python collector/make_hwpx.py --all       # data/handouts/<회차>.hwpx
python collector/make_hwpx.py --id 2026-W34 --out 전달사항.hwpx
```

`templates/전달사항_양식.hwpx` 를 템플릿으로 두고 **표의 행만 갈아 끼웁니다.** hwpx 는 글꼴과
문단모양이 header.xml 에 모여 있어서, 빈 문서에서 만들면 실제 배포 문서와 모양이 달라집니다.

지시사항의 `title` 이 ❍ 줄, `text` 가 ` - ` 세부 줄, `dept` 가 추진부서 칸이 됩니다.
부서를 여러 개 쓰려면 `"교육협력과 / 교육지원청"` 처럼 `/` 로 나눕니다.
만들어진 파일은 웹 화면의 회의 요약 탭에서 **전달사항 내려받기** 버튼으로 받을 수 있습니다.

> **주의**: 대변인실 문서에는 생중계에 나오지 않은 내용도 들어갑니다. 회의 말미에 생중계를 끄고
> 논의하는 시간이 있기 때문입니다. 이 서비스가 만드는 전달사항은 **생중계된 부분만** 담고 있으므로
> 대변인실 문서를 대체하지 않습니다. 초안으로 쓰고 빠진 항목을 채워 넣는 용도로 보세요.

### 1.5단계를 왜 두었나

사전(`glossary.json`)은 실수를 하나하나 목격해야만 잡습니다. 그런데 자막 오류는 대부분
**바로 앞 문장에 답이 있습니다.**

```
"정책 기획과로 가겠습니다."  →  "네. 정책계과 말씀드리겠습니다."     (= 정책기획과)
"다음 감사 관실로 가죠."     →  "예. 검사관실 말씀드리겠습니다."     (= 감사관실)
```

사회자가 부서를 부르고 그 부서가 답하는 구조라, 문맥을 읽으면 풀립니다. 사전은 고유명사
고정용으로 남기고 나머지는 LLM이 맡습니다. 화자도 여기서 붙입니다(바뀔 때만 표시하고 이어받음).

자동자막은 한 줄이 16자쯤으로 잘게 쪼개져 있어(26분에 591줄) 먼저 문장 단위로 합칩니다.
26분 회의가 150문장이 되고, 출력 토큰이 28%쯤 줄면서 읽기도 좋아집니다.

## 화면

| 탭 | 내용 |
|---|---|
| 홈 | 검색창, 수집 지표, 최근 회의, 회차별 자막·요약 진행 상태 |
| 회의 요약 | 영상 + 한눈에 보기 + 요약 + 처리 결과 + 안건 + 지시사항 + 자막 교정 내역 |
| 회의록 전문 | 화자별로 끊어 읽기, 시간별/이어보기 전환, 회의록 내 검색, 자막 원문 대조, 복사·TXT |
| 지시사항 | 부서·유형·이행 상태로 걸러 보고, 이후 회차 보고와 연결 |
| 통합검색 | 안건·지시·처리결과·발언 전문을 한 번에 |

모든 항목에 타임스탬프가 붙어 있어, 누르면 영상의 해당 지점으로 이동합니다.
**자동자막 기반이라 오류가 섞입니다. 요약을 그대로 믿지 말고 원문으로 확인할 수 있게 만든 구조입니다.**

## ⚠️ 러너는 자체 호스팅이어야 합니다

GitHub이 제공하는 클라우드 러너(미국 Azure 데이터센터 IP)에서 yt-dlp 로 유튜브 자막을 받으면
`Sign in to confirm you're not a bot` 으로 **차단됩니다**(2026-08 실측).
그래서 `collect.yml` 은 `runs-on: self-hosted` 입니다. 사무실 PC에 러너를 설치해 국내 IP로 실행합니다.
공공기관 사이트가 해외 IP를 막는 경우도 있어, 게시판 접근 문제까지 함께 해결됩니다.

화면 배포(`pages.yml`)는 외부 접속이 없으므로 클라우드 러너를 씁니다.

> 나중에 상황이 바뀌었는지 보려면 Actions에서 **접근성 점검 (진단용)** 을 수동 실행하세요.
> 게시판·자막 목록·자막 추출 세 단계를 클라우드 러너에서 시험합니다. 모두 통과하면
> `collect.yml` 의 `runs-on` 을 `ubuntu-latest` 로 바꿔 러너 없이 운영할 수 있습니다.

## 설치

### 1. 저장소

```bash
git init && git add -A && git commit -m "init"
gh repo create jbe-weekly-policy-meeting --public --source=. --push
```

Settings → Pages → Source 를 **GitHub Actions** 로 지정합니다.

### 2. 자체 호스팅 러너 (사무실 PC, Windows)

Settings → Actions → Runners → **New self-hosted runner** → Windows 를 고르고 안내대로 실행합니다.
마지막에 서비스로 등록하면 부팅 시 자동 실행됩니다.

- 워크플로가 `shell: bash` 를 쓰므로 **Git for Windows** 가 설치되어 있어야 합니다.
- 라벨을 붙였다면 저장소 Variables 에 `RUNNER_LABEL` 로 등록하세요.

### 3. 키

Settings → Secrets and variables → Actions

| 종류 | 이름 | 값 |
|---|---|---|
| Secret | `GEMINI_API_KEY` | Google AI Studio 키 |
| Secret | `OPENAI_API_KEY` | (OpenAI를 쓸 경우) |
| Variable | `LLM_PROVIDER` | `gemini`(기본) 또는 `openai` |
| Variable | `GEMINI_MODEL` | 기본 `gemini-2.5-flash` |

키가 아직 없어도 됩니다. 그때는 `mode: transcripts-only` 로 돌려 자막부터 모으세요.

### 4. 첫 수집

Actions → **주간정책회의 수집** → Run workflow → mode `all`

## 로컬에서

```bash
# 수집기
pip install -r collector/requirements.txt
python collector/fetch_transcripts.py --check
python collector/fetch_transcripts.py --all
python collector/fetch_transcripts.py --video MeLmER3fq_w --srt 회의록.srt   # 영상 하나만
python collector/run.py --summary-only                                       # 요약만 다시
python collector/tests/test_parse.py                                         # 파서 회귀 테스트

# 화면
npm install
npm run dev      # http://localhost:3000
npm run build    # dist/
npm run lint     # tsc --noEmit
```

`npm run dev` 는 `data/` 를 그대로 읽습니다. 빌드 결과로 확인하려면 `dist/` 에 `data/` 를 복사하세요.

## 자막 후보정 사전

유튜브 자동자막은 고유명사에 특히 약합니다. 실제로 확인된 오류들:

| 자막 | 실제 |
|---|---|
| 주관 정책일 | 주간정책회의 |
| 청년 콘텐츠 공무전 | 청렴 콘텐츠 공모전 |
| 노사 협력가 | 노사협력과 |
| 창애인재 교육과 | 창의인재교육과 |
| 교육감지지 사항 | 교육감 지시사항 |
| 합폭 전담 변호사 | 학폭 전담 변호사 |

`collector/glossary.json` 에 정규식으로 등록하면 수집할 때마다 자동 교정되고, 바뀐 문장은
`raw` 에 원문을 남겨 화면에서 대조할 수 있습니다. 회의를 돌릴수록 새 오류가 나오므로
**계속 늘려 가는 파일**입니다. `departments` 는 조직도 기준으로 한 번 정리해 두면 부서 태깅이 정확해집니다.

> **중요 — 교정은 문장으로 합친 뒤에 겁니다.**
> 처음에는 자막을 받는 즉시(2~3초짜리 조각 상태에서) 사전을 적용했는데, 그러면
> `노사\s*협력가` 같은 규칙이 두 줄에 걸쳐 있을 때 아무것도 잡히지 않습니다. 실제로
> 사전에 52개 규칙이 있는데도 회차당 2~5줄만 교정됐습니다. 지금은 `segment.py` 가
> 문장으로 합친 다음 교정합니다.

## 발언 단위 정리 (`collector/segment.py`)

자동자막은 2~3초마다 끊겨서 회차당 1,200줄이 됩니다. 그대로는 못 읽습니다.

    python collector/segment.py --all      # data/refined/<회차>.json 생성

- 문장으로 합칩니다 (1,192줄 → 268문장)
- `>>` 를 **문단 경계로만** 씁니다. 화자 전환 표시처럼 보이지만 20초에 한 번꼴로
  찍히고, 같은 사람이 말을 이어 가는 중에도 찍힙니다. 이걸로 '교육감 → 부서 → 교육감'
  번갈이를 가정해 화자를 채워 봤더니 보고 본문이 통째로 교육감 발언으로 뒤집혔습니다.
- 자기소개("○○과 말씀드리겠습니다")가 나오는 자리만 화자를 **확정**하고, 거기서부터
  다음 부서 자기소개까지를 그 부서의 **보고 구간(block)** 으로 표시합니다.

### 사람이 채우는 부분 — `data/human/<회차>.json`

발언마다의 화자와 문맥이 필요한 교정은 자동으로 안 됩니다. 사람이 이 파일에 적습니다.

```json
{
  "splits":   [176, 921],
  "speakers": { "10": "교육감", "139": "대변인실", "176": "미래교육과" },
  "fixes":    { "149": "9월 1일부터 교육지원청 누리집 …" }
}
```

키는 문장의 시작 초입니다. `splits` 는 자막이 놓친 화자 전환 자리,
`speakers` 는 그 발언의 화자, `fixes` 는 그 문장의 교정된 전문입니다.
**자막을 다시 받거나 사전을 고쳐서 `segment.py` 를 다시 돌려도 이 파일이 이깁니다.**
사람 손이 가장 비싼 자원인데 코드가 그걸 덮어쓰면 안 되기 때문입니다.

현재 상태:

| 회차 | 교정된 문장 | 화자 확정 |
|---|---|---|
| 2026-W31 | 8 / 268 | 23 / 93 |
| 2026-W32 | 14 / 282 | 23 / 120 |
| 2026-W33 | 11 / 286 | 18 / 123 |
| **2026-W34** | **70 / 149** | **82 / 84** |

W34 만 사람 손을 거쳤습니다. 나머지는 사전 교정과 자기소개 인식까지만 돼 있습니다.

> 요약(`data/meetings/`)의 `quote` 는 교정본에 **글자 그대로** 있어야 합니다.
> 교정으로 문장이 바뀌면 인용도 같이 맞춰야 합니다. 확인은 이렇게 합니다.
>
> ```python
> ref = ' '.join(c['text'] for c in refined['cues'])
> assert all(d['quote'] in ref for d in meeting['directives'] if d.get('quote'))
> ```

## 비용

Gemini 3.6 Flash 유료 기준(입력 $0.75 / 출력 $3.75 per 1M), 60분 회의 한 건에

| 단계 | 입력 | 출력 | 비용 |
|---|---|---|---|
| 1.5단계 교정·화자 | 약 34k | 약 28k | 약 190원 |
| 2단계 요약 | 약 25k | 약 5k | 약 55원 |

주 1회이므로 **월 1,100원 안팎**입니다. `refine.py --dry-run` 으로 돌리기 전에 확인할 수 있습니다.
웹페이지는 정적이라 방문자 수와 무관하게 API 비용이 들지 않습니다.

> **모델 이름은 바뀝니다.** 구글이 구형 모델 제공을 중단하면 `404 ... no longer available` 이 납니다.
> `collector/config.py` 의 `GEMINI_MODEL` 기본값을 고치거나 환경변수로 덮어쓰세요.
> 단가가 달라지면 `collector/refine.py` 의 `PRICE_IN, PRICE_OUT` 도 같이 고칩니다.
> ```powershell
> $env:GEMINI_MODEL = "gemini-3.6-flash"
> ```

## 한계

- **화자는 추정입니다.** 자막에 화자 정보가 없어 말투와 문맥으로 판단하고, 확신이 없으면 비워 둡니다.
  정확도가 더 필요하면 오디오를 받아 Whisper + 화자분리(pyannote)를 붙이는 방법이 있습니다.
- **교정도 완벽하지 않습니다.** 화면에서 자막 원문을 나란히 볼 수 있게 해 둔 이유입니다.
- **자동자막이 늦게 생성될 수 있습니다.** 업로드 직후에는 없을 수 있고, 다음 실행에서 재시도합니다.
- **요약은 참고용입니다.** 공식 회의록이 아닙니다.
- 지시사항의 ‘같은 부서 보고 있음’은 부서가 같아 추정한 것이지 확정이 아닙니다.

## 파일

```
.github/workflows/
  collect.yml     3시간마다 수집 (자체 호스팅 러너)
  pages.yml       npm build + data → GitHub Pages
  probe.yml       클라우드 러너에서 접근 가능한지 진단
collector/
  fetch_transcripts.py  1단계 · 자막 확보 (단독 실행 가능)
  refine.py             1.5단계 · 문장 합치기 + 문맥 교정 + 화자 (단독 실행 가능)
  run.py                1 → 1.5 → 2단계 전체
  board.py              게시판 목록·상세 파싱
  captions.py           자막 추출·파싱 (json3 / vtt / API)
  correct.py            사전 기반 후보정
  glossary.json         오인식 사전 + 부서 목록 (회차를 돌릴수록 늘려 간다)
  summarize.py          LLM 요약 (Gemini / OpenAI)
  tests/                픽스처 기반 회귀 테스트
data/
  index.json            회차 목록 + 단계별 진행 상태
  transcripts/*.json    1단계 · 자막 원문 + 사전 교정
  refined/*.json        1.5단계 · 문맥 교정 + 화자
  meetings/*.json       2단계 · 요약
src/                    화면 (React + Tailwind, KRDS 토큰)
```
