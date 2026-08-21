---
name: jbe-weekly-meeting
description: 전북특별자치도교육청 교육감 주간정책회의 영상을 회의록·요약·지시사항으로 정리해 웹에 올린다. 새 회차 영상이 게시판에 올라왔을 때 오디오를 받아쓰고, 목소리로 화자를 갈라내고, 안건·교육감 지시사항·지난 지시 처리결과를 뽑아 data/ 에 저장한 뒤 깃허브에 올린다. 주간정책회의 정리, 회의록 만들기, 새 회차 수집, 지시사항 정리를 요청받았을 때 사용한다.
---

# 주간정책회의 정리

저장소: `C:\work\jbe-weekly-policy-meeting` · 공개 웹: https://kain9012-bit.github.io/jbe-weekly-policy-meeting/

교육감이 매주 주관하는 주간정책회의는 유튜브로 생중계되고 게시판에 올라온다.
이걸 **교육청 직원이 읽을 수 있는 회의록과 지시사항 트래커**로 바꾸는 작업이다.

구조는 이렇다. **수집은 자동, 정리는 요청, 열람은 웹.**
LLM API를 쓰지 않는다. 요약과 화자 배정은 이 세션에서 사람(Claude)이 직접 한다.

---

## 절대 규칙

1. **인용문을 지어내지 않는다.** `quote` 는 회의록에 **글자 그대로** 있는 문장이어야 한다.
   요약하면서 문장을 다듬다가 어긋나기 쉽다. 저장 전에 `scripts/verify.py` 로 확인한다.
   지어낸 인용 하나가 이 서비스의 신뢰를 통째로 무너뜨린다.

2. **회차는 오래된 것부터 정리한다.** 처리결과(`followups`)는 이전 회차의 지시를 가리켜야
   하는데, 최신 회차부터 정리하면 가리킬 대상이 없어 전부 빈 값이 된다.
   실제로 그렇게 만들었다가 9건 중 1건만 연결돼 있었다.

3. **추측을 확정처럼 보이게 하지 않는다.** 근거가 없으면 비워 둔다.
   부서명이 같다는 이유로 지시와 보고를 잇지 않는다. 화자를 모르면 사람에게 묻는다.

4. **내부 값을 화면에 내보내지 않는다.** `2026-W35` 같은 회차 ID, 자막 줄 수, 군집 번호,
   출처 표시는 전부 시스템 사정이지 회의 내용이 아니다. 읽는 사람이 그걸로 할 수 있는
   일이 없으면 화면에 두지 않는다.

5. **오디오는 저장소에 넣지 않는다.** `.gitignore` 에 `data/audio/` 가 있다.
   회차당 25MB이고 유튜브에서 언제든 다시 받을 수 있다.

---

## 절차

### 0. 새 회차가 있는지 확인

```bat
수집.bat
```

게시판을 보고 아직 자막을 안 받은 회차만 받는다. 회차 ID는 게시일의 ISO 주차(`2026-W35`)다.
**유튜브 자막은 버리지 않는다** — 뒤에서 받아쓰기 누락을 잡는 대조본으로 쓴다.

### 1. 오디오 받기 (사용자 노트북에서)

```bat
오디오받기.bat
```

유튜브는 데이터센터 IP를 막으므로 **반드시 사용자 컴퓨터에서** 실행해야 한다.
클라우드에서 돌리면 `Sign in to confirm you're not a bot` 이 뜬다.
받은 파일을 `device_stage_files` 로 가져온 뒤 `data/audio/` 에 둔다.

### 2. 받아쓰기 + 자막 대조 + 화자 분리

```bash
python collector/transcribe.py --id 2026-W35
```

60분 회의에 **35~40분** 걸린다. 오래 걸리니 백그라운드로 돌리고 10분 간격으로 확인한다.
받아쓰기가 끝나면 화자 분리 전에 한 번 저장하므로, 뒤에서 죽어도 다시 안 해도 된다.

무엇을 하는지와 왜 그렇게 하는지는 `references/pipeline.md` 에 있다.

### 3. 발언 단위로 정리

```bash
python collector/segment.py --from-asr --id 2026-W35
```

이때 **화자가 몇 개나 자동으로 붙었는지** 본다. 보통 절반쯤 붙는다.

### 4. 화자와 교정 채우기 — 여기가 사람이 하는 일

발언 목록을 출력해 놓고 읽는다.

```bash
python3 -c "
import json,sys; sys.path.insert(0,'collector')
from segment import from_asr
d=from_asr(json.load(open('data/asr/2026-W35.json')), json.load(open('data/transcripts/2026-W35.json')))
n=0
for c in d['cues']:
    if c.get('turnStart'):
        n+=1; print(f\"{n:>2} t={c['t']:<5} {int(c['t'])//60}:{int(c['t'])%60:02d} {c.get('speaker','—'):<12} {c['text'][:60]}\")
"
```

`data/human/2026-W35.json` 에 적는다. 키는 **발언 시작 초**다.

```json
{
  "speakers": { "174": "미래교육과", "295": "예산과" },
  "fixes":    { "341": "현재 위원회가 몇 개 정도 있어요?" }
}
```

- 회의는 `교육감 → 부서 보고 → 교육감 질의 → 부서 답변` 이 반복된다.
  교육감이 "다음 ○○과로 가시죠" 라고 부르면 그 다음이 그 부서다.
- 반복해서 틀리는 오인식은 `data/human/` 이 아니라 `collector/glossary.json` 에 넣는다.
  그래야 다음 회차에서도 자동으로 걸린다. 지금 110개 규칙이 쌓여 있다.
- 자주 틀리는 자리는 `references/pitfalls.md` 에 정리해 두었다. **먼저 읽으면 시간이 준다.**

고쳤으면 다시 돌린다.

```bash
python collector/segment.py --from-asr --id 2026-W35
```

### 5. 요약 쓰기

`data/meetings/2026-W35.json` 을 직접 쓴다. 구조는 이전 회차 파일을 그대로 따른다.
`summary` / `highlights` / `agenda` / `directives` / `followups`.

**처리결과(`followups`)를 쓸 때는 반드시 이전 회차의 `directives` 를 펼쳐 놓는다.**

```bash
python3 -c "
import json,glob
for f in sorted(glob.glob('data/meetings/*.json')):
    m=json.load(open(f))
    for d in m['directives']: print(f\"{d['id']:<14} {d['dept']:<20} {d['text'][:70]}\")
"
```

이었는지 판단하는 기준은 하나다 — **회의에서 그 지시를 짚어 보고했는가.**
주제가 비슷하다는 건 근거가 아니다. 판단이 갈리는 실제 사례는
`references/lessons.md` 의 '무엇을 잇고 무엇을 안 잇나' 에 있다.

### 6. 검증 — 반드시 통과시킨다

```bash
python scripts/verify.py
```

인용문·부서명·연결 순서·화자 누락을 검사한다. **하나라도 걸리면 고치기 전에 발행하지 않는다.**
여기서 걸리는 항목은 전부 실제로 한 번씩 사고가 났던 것들이다.

### 7. 마무리

```bash
python collector/make_hwpx.py --all     # 대변인실 양식 전달사항
npm run build                            # 화면 빌드 확인
```

`data/index.json` 의 회차 정보(`turnCount`, `speakerTurns`, `depts`, `directiveCount`)를
갱신한다. 그리고 사용자에게 푸시 명령을 준다.

```powershell
cd C:\work\jbe-weekly-policy-meeting
git add -A
git commit -m "2026년 ○월 ○주 주간정책회의 정리"
git push
```

**푸시는 사용자가 한다.** 자격증명을 다루지 않는다.

---

## 참고 자료

| 파일 | 내용 |
|---|---|
| `references/pipeline.md` | 각 단계가 무엇을 하고 왜 그렇게 하는지 |
| `references/lessons.md` | 화면·데이터 설계에서 실제로 틀렸다가 고친 것들 |
| `references/pitfalls.md` | 받아쓰기·화자 분리가 자주 틀리는 자리 |
| `references/departments.json` | 본청 부서 목록 (기구도 기준) |
| `scripts/verify.py` | 발행 전 검증 |

## 사용자에게 물어야 할 때

- 회의에서 부서를 특정할 수 없는 발언이 있을 때 (추측해서 채우지 않는다)
- 지시인지 단순 언급인지 애매할 때
- 생중계가 꺼진 구간이 의심될 때 — 실제로 "생방송 끄고 할까요?" 가 녹화된 적이 있다.
  대변인실 문서에는 있는데 회의록에 없는 항목이 그래서 생긴다.
