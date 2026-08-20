"""1.5단계 · 회의록 전문 교정 + 화자 태깅.

    python collector/refine.py                 # 아직 교정 안 된 회차
    python collector/refine.py --all           # 전부 다시
    python collector/refine.py --id 2026-W34
    python collector/refine.py --dry-run       # 호출 없이 토막 수·토큰·비용만 계산

1단계(`fetch_transcripts.py`)가 만든 `data/transcripts/<ID>.json` 을 읽어
`data/refined/<ID>.json` 을 만든다. 원본을 덮어쓰지 않으므로 각 단계를 따로 다시 돌릴 수 있다.

## 왜 LLM 인가
사전(`glossary.json`)은 내가 실수를 하나하나 목격해야만 잡는다. 그런데 자막 오류는
대부분 앞 문장에 답이 있다.
    "정책 기획과로 가겠습니다."  →  "네. 정책계과 말씀드리겠습니다."
    "다음 감사 관실로 가죠."    →  "예. 검사관실 말씀드리겠습니다."
사회자가 부서를 부르고 그 부서가 답하는 구조라, 문맥을 읽으면 바로 풀린다.
사전은 고유명사 고정용으로 남기고 나머지는 여기서 처리한다.

## 화자
자막에는 화자 정보가 없다. 말투와 문맥으로 추정하되 **바뀔 때만** 표시하게 하고,
나머지 줄은 앞 화자를 이어받는다. 출력 토큰이 줄고, 사람이 읽는 회의록 모양과도 맞다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_transcripts as FT  # noqa: E402
from config import (LLM_PROVIDER, OPENAI_MODEL, REFINE_MODEL, REFINE_OVERLAP,  # noqa: E402
                    REFINE_WINDOW_SEC, REFINED_DIR, TRANSCRIPTS_DIR)
from correct import departments  # noqa: E402

# 모델별 유료 단가 (1M 토큰당 달러, 2026-08 기준). 값이 바뀌면 여기만 고친다.
PRICES = {
    "gemini-3.7-flash":      (0.75, 3.75),
    "gemini-3.6-flash":      (0.75, 3.75),
    "gemini-3.5-flash":      (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}
DEFAULT_PRICE = (0.75, 3.75)
USD_KRW = 1450


def price_of(model: str) -> tuple[float, float]:
    # 긴 이름부터 본다. 'gemini-3.5-flash-lite' 가 'gemini-3.5-flash' 로 먼저 걸리면
    # lite 를 비싼 단가로 계산해 버린다.
    for name in sorted(PRICES, key=len, reverse=True):
        if model.startswith(name):
            return PRICES[name]
    return DEFAULT_PRICE


class RefineError(RuntimeError):
    pass


def model_error_hint(exc: Exception, model: str = "") -> str:
    """모델 이름 문제는 스택 트레이스보다 '뭘 바꾸면 되는지'가 필요하다."""
    msg = str(exc)
    model = model or REFINE_MODEL
    if "404" in msg and ("no longer available" in msg or "NOT_FOUND" in msg):
        import re as _re
        m = _re.search(r"use models/([\w.\-]+)", msg)
        suggest = m.group(1) if m else "최신 flash 모델"
        return (
            f"모델 '{model}' 을(를) 쓸 수 없습니다. 구글이 제공을 중단했습니다.\n"
            f"  → GEMINI_MODEL(전체) 또는 REFINE_MODEL/SUMMARY_MODEL(단계별) 을 '{suggest}' 로 바꾸세요.\n"
            f"  예) $env:GEMINI_MODEL = \"{suggest}\"\n"
            f"--- 원본 오류 ---\n{msg[:400]}"
        )
    return msg


PROMPT = """당신은 전북특별자치도교육청 주간정책회의의 회의록을 다듬는 담당자입니다.
아래는 생중계 영상의 **자동생성 자막** 한 토막입니다. 두 가지를 해 주세요.

## 1. 교정
자동자막이라 특히 고유명사가 자주 틀립니다. **문맥을 읽고** 바로잡으세요.
정답이 바로 앞 문장에 있는 경우가 많습니다. 실제 예:
- "정책 기획과로 가겠습니다" 다음의 "정책계과 말씀드리겠습니다" → "정책기획과 말씀드리겠습니다"
- "다음 감사 관실로 가죠" 다음의 "검사관실 말씀드리겠습니다" → "감사관실 말씀드리겠습니다"
- "제목과 말씀드리겠습니다" → "재무과 말씀드리겠습니다"
- "청년 콘텐츠 공무전" → "청렴 콘텐츠 공모전"

지킬 것:
- **말한 내용을 그대로 옮기세요. 요약·생략·윤문 금지.** 잘못 들린 낱말만 고칩니다.
- 각 줄은 반드시 하나씩 대응해야 합니다. 줄을 합치거나 나누지 마세요.
- "어", "그", "네" 같은 군말은 **그대로 둡니다.** 실제 발언 기록이어야 합니다.
- 고칠 데가 없으면 원문을 그대로 다시 쓰세요.
- 무슨 말인지 알 수 없으면 억지로 만들지 말고 원문을 유지하세요.

## 2. 화자
자막에 화자 표시가 없습니다. 말투와 문맥으로 추정하세요.
- 지시·질문·당부하는 쪽은 대개 **교육감**입니다.
- "○○과 말씀드리겠습니다", "이상입니다" 로 보고하는 쪽은 그 **부서**입니다.
- **화자가 바뀌는 줄에만** speaker 를 넣으세요. 이어지는 줄에는 넣지 마세요.
- **확신이 없으면 넣지 마세요.** 지어내지 마세요.

## 부서 후보
{departments}

## 직전 맥락 (참고용, 출력하지 마세요)
{context}

## 이번 토막 (i = 줄 번호)
{lines}

## 출력
아래 형태의 JSON 하나만 출력하세요. 설명·코드펜스 없이 JSON만.
이번 토막의 {count}개 줄을 **하나도 빠짐없이, 같은 순서로** 담아야 합니다.
{{"cues":[{{"i":0,"text":"교정된 문장","speaker":"교육감"}},{{"i":1,"text":"교정된 문장"}}]}}
"""


# 문장 끝은 문장부호로만 판단한다.
# '다/요/가/네' 같은 낱글자까지 종결로 보면 "자치단체장 직무평가 결과가" 처럼
# 조사에서 문장이 끊긴다. 자동자막이 마침표는 꽤 정확히 넣어주므로 이것으로 충분하다.
# 부호가 없는 긴 구간은 max_chars 로 끊는다.
SENT_END = re.compile(r"[.?!]\s*$")


def merge_cues(cues: list[dict], max_chars: int = 140) -> list[dict]:
    """잘게 쪼개진 자막 줄을 문장 단위로 합친다.

    json3 자동자막은 26분 회의를 591줄로 쪼갠다. 한 줄이 16자 남짓이라
    "어 7월" / "자치단체장 직무평가 결과가" 처럼 문장 조각만 남는다.
    이대로 교정에 넘기면 LLM 이 문맥을 못 읽고, 줄마다 JSON 껍데기가 붙어 출력도 커진다.
    시각은 **합쳐진 첫 줄의 것**을 쓴다 — 타임스탬프를 눌렀을 때 발언 처음으로 가야 한다.
    """
    out: list[dict] = []
    buf: list[dict] = []

    def flush() -> None:
        if not buf:
            return
        text = " ".join(c["text"] for c in buf).strip()
        raw = " ".join(c.get("raw", c["text"]) for c in buf).strip()
        item = {"t": buf[0]["t"], "text": text}
        if raw != text:
            item["raw"] = raw
        out.append(item)
        buf.clear()

    for c in cues:
        buf.append(c)
        joined = " ".join(x["text"] for x in buf)
        if SENT_END.search(joined) or len(joined) >= max_chars:
            flush()
    flush()
    return out


def chunk(cues: list[dict], window_sec: int) -> list[tuple[int, int]]:
    """[(시작 인덱스, 끝 인덱스)] — 시간 창 기준으로 자른다."""
    if not cues:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    edge = cues[0]["t"] + window_sec
    for i, c in enumerate(cues):
        if c["t"] >= edge:
            spans.append((start, i))
            start = i
            edge = c["t"] + window_sec
    spans.append((start, len(cues)))
    return spans


def _call(prompt: str, model: str = "") -> str:
    model = model or REFINE_MODEL
    if LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types
        from config import GEMINI_API_KEY
        if not GEMINI_API_KEY:
            raise RefineError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        client = genai.Client(api_key=GEMINI_API_KEY)
        try:
            res = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,                # 교정은 창의성이 필요 없다
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    # 함수 호출을 안 쓰는데 SDK 가 매번 경고를 찍어 로그를 어지럽힌다.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise RefineError(model_error_hint(exc, model)) from None
        return res.text
    from openai import OpenAI
    from config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        raise RefineError("OPENAI_API_KEY 가 설정되지 않았습니다.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    res = client.chat.completions.create(
        model=OPENAI_MODEL, temperature=0.1,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return res.choices[0].message.content


def _parse(raw: str) -> list[dict]:
    import re
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.S)
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        raise RefineError(f"JSON 을 찾지 못했습니다: {raw[:200]}")
    data = json.loads(raw[s:e + 1])
    out = data.get("cues")
    if not isinstance(out, list):
        raise RefineError("cues 배열이 없습니다.")
    return out


def refine_chunk(cues: list[dict], context: list[dict], model: str = "") -> list[dict]:
    """토막 하나를 교정한다. 줄 수가 안 맞으면 그 토막은 원문을 유지한다."""
    lines = "\n".join(f'{i}\t[{c["t"] // 60}:{c["t"] % 60:02d}]\t{c["text"]}'
                      for i, c in enumerate(cues))
    ctx = "\n".join(c["text"] for c in context) or "(없음 — 회의 시작)"
    prompt = PROMPT.format(departments=", ".join(departments()), context=ctx,
                           lines=lines, count=len(cues))

    got = _parse(_call(prompt, model))
    by_i = {int(x["i"]): x for x in got if isinstance(x, dict) and "i" in x}

    # 빠진 줄이 있으면 그 줄만 원문으로 채운다. 통째로 버리지 않는다.
    missing = 0
    out: list[dict] = []
    for i, c in enumerate(cues):
        got_i = by_i.get(i)
        if got_i is None or not str(got_i.get("text", "")).strip():
            missing += 1
            out.append({"t": c["t"], "text": c["text"]})
            continue
        item = {"t": c["t"], "text": str(got_i["text"]).strip()}
        sp = str(got_i.get("speaker", "")).strip()
        if sp:
            item["speaker"] = sp
        out.append(item)
    if missing:
        print(f"      ! {missing}/{len(cues)}줄이 응답에 없어 원문을 유지했습니다")
    return out


def refine_doc(tr: dict, *, window_sec: int, verbose: bool = True,
               merge: bool = True, model: str = "") -> dict:
    model = model or REFINE_MODEL
    src_count = len(tr["cues"])
    cues = merge_cues(tr["cues"]) if merge else tr["cues"]
    spans = chunk(cues, window_sec)
    if verbose:
        print(f"  {tr['id']} · 자막 {src_count}줄 → 문장 {len(cues)}줄 → {len(spans)}토막")

    refined: list[dict] = []
    changed = 0
    for n, (a, b) in enumerate(spans, 1):
        part = cues[a:b]
        ctx = cues[max(0, a - REFINE_OVERLAP):a]
        if verbose:
            print(f"    토막 {n}/{len(spans)} ({part[0]['t'] // 60}~{part[-1]['t'] // 60}분, {len(part)}줄)")
        done = refine_chunk(part, ctx, model)
        for src, dst in zip(part, done):
            base = src.get("raw", src["text"])       # 사전 교정 전 ASR 원문
            if dst["text"] != base:
                dst["raw"] = base
            if dst["text"] != src["text"]:
                changed += 1
        refined += done

    # 화자는 바뀔 때만 나온다. 나머지 줄은 앞 화자를 이어받는다.
    cur = ""
    speakers = 0
    for c in refined:
        if c.get("speaker"):
            cur = c["speaker"]
            speakers += 1
        elif cur:
            c["speaker"] = cur
    named = sum(1 for c in refined if c.get("speaker"))

    if verbose:
        print(f"    교정 {changed}줄 · 화자 전환 {speakers}회 · 화자 표시 {named}/{len(refined)}줄")

    return {
        **{k: v for k, v in tr.items() if k not in ("cues", "glossaryHits", "_sample", "_sampleNote")},
        "refinedAt": FT.now_iso(),
        "refineModel": model if LLM_PROVIDER == "gemini" else OPENAI_MODEL,
        "chunkCount": len(spans),
        "changedLines": changed,
        "speakerTurns": speakers,
        "sourceCueCount": src_count,
        "cueCount": len(refined),
        "charCount": sum(len(c["text"]) for c in refined),
        "cues": refined,
    }


def estimate(tr: dict, window_sec: int, merge: bool = True, model: str = "") -> dict:
    price_in, price_out = price_of(model or REFINE_MODEL)
    """호출 없이 토막 수·토큰·비용을 계산한다."""
    cues = merge_cues(tr["cues"]) if merge else tr["cues"]
    spans = chunk(cues, window_sec)
    prompt_overhead = 900                       # 지시문 + 부서 목록
    tok_in = tok_out = 0
    biggest = 0
    for a, b in spans:
        part = cues[a:b]
        ch = sum(len(c["text"]) for c in part)
        line_tok = (ch + len(part) * 14) * 1.1 / 1  # 번호·타임스탬프 접두 포함
        tok_in += prompt_overhead + line_tok
        out = (ch + len(part) * 12) * 1.1          # 교정문 + JSON 껍데기
        tok_out += out
        biggest = max(biggest, out)
    cost = tok_in / 1e6 * price_in + tok_out / 1e6 * price_out
    return {"chunks": len(spans), "lines": len(cues), "in": tok_in, "out": tok_out,
            "maxOut": biggest, "usd": cost, "krw": cost * USD_KRW}


def plain_text(cues: list[dict]) -> str:
    """요약 단계에 넘길 회의록. 화자는 바뀔 때만 적어 토큰을 아낀다."""
    out, cur = [], ""
    for c in cues:
        sp = c.get("speaker", "")
        head = f"{sp}: " if sp and sp != cur else ""
        if sp:
            cur = sp
        out.append(f'[{c["t"] // 60}:{c["t"] % 60:02d}] {head}{c["text"]}')
    return "\n".join(out)


def corrections_from(cues: list[dict]) -> list[dict]:
    """교정 내역을 실제 차이에서 뽑는다. LLM 자기 보고가 아니라 사실이다."""
    seen: dict[tuple[str, str], int] = {}
    for c in cues:
        raw = c.get("raw")
        if not raw or raw == c["text"]:
            continue
        key = (raw.strip(), c["text"].strip())
        seen[key] = seen.get(key, 0) + 1
    return [{"from": a, "to": b, "count": n}
            for (a, b), n in sorted(seen.items(), key=lambda kv: -kv[1])]


def load_best(meeting_id: str) -> tuple[dict, bool]:
    """교정본이 있으면 그것을, 없으면 자막 원본을 돌려준다. (문서, 교정본인지)"""
    p = REFINED_DIR / f"{meeting_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")), True
    q = TRANSCRIPTS_DIR / f"{meeting_id}.json"
    if q.exists():
        return json.loads(q.read_text(encoding="utf-8")), False
    raise RefineError(f"{meeting_id} 의 자막이 없습니다.")


def main() -> int:
    ap = argparse.ArgumentParser(description="회의록 교정 + 화자 태깅 (1.5단계)")
    ap.add_argument("--all", action="store_true", help="이미 교정된 회차도 다시")
    ap.add_argument("--id", help="특정 회차만 (예: 2026-W34)")
    ap.add_argument("--window", type=int, default=REFINE_WINDOW_SEC, help="토막 길이(초)")
    ap.add_argument("--dry-run", action="store_true", help="호출 없이 토막·토큰·비용만")
    ap.add_argument("--model", default="", help="이번 실행에만 쓸 모델 (예: gemini-3.5-flash-lite)")
    ap.add_argument("--out", help="결과를 다른 경로에 저장 (모델 비교용). 지정하면 index 는 건드리지 않는다")
    args = ap.parse_args()
    model = args.model or REFINE_MODEL

    files = sorted(TRANSCRIPTS_DIR.glob("*.json"))
    if not files:
        print("자막이 없습니다. 먼저 `python collector/fetch_transcripts.py --all` 을 실행하세요.")
        return 1

    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    if args.id:
        docs = [d for d in docs if d["id"] == args.id]
    if not args.all and not args.id:
        docs = [d for d in docs if not (REFINED_DIR / f'{d["id"]}.json').exists()]

    if args.dry_run:
        pin, pout = price_of(model)
        print(f"모델 {model} (입력 ${pin}/출력 ${pout} per 1M) · 토막 길이 {args.window}초\n")
        print(f"{'회차':<10}{'자막줄':>7}{'문장줄':>7}{'토막':>5}{'입력':>9}{'출력':>9}{'최대출력':>9}{'비용':>8}")
        print("-" * 70)
        tot = {"in": 0, "out": 0, "krw": 0}
        for d in docs:
            e = estimate(d, args.window, model=model)
            for k in tot:
                tot[k] += e[k]
            print(f'{d["id"]:<10}{d["cueCount"]:>7}{e["lines"]:>7}{e["chunks"]:>5}'
                  f'{e["in"] / 1000:>8.1f}k{e["out"] / 1000:>8.1f}k'
                  f'{e["maxOut"] / 1000:>8.1f}k{e["krw"]:>7.0f}원')
        print("-" * 70)
        print(f'{"합계":<10}{"":>7}{"":>7}{"":>5}{tot["in"] / 1000:>8.1f}k'
              f'{tot["out"] / 1000:>8.1f}k{"":>9}{tot["krw"]:>7.0f}원')
        print("\n최대출력이 16k 토큰(모델 상한)에 가까우면 --window 를 줄이세요.")
        return 0

    if not docs:
        print("새로 교정할 회차가 없습니다.")
        return 0

    index = FT.load_index()
    failures = 0
    for d in docs:
        try:
            out = refine_doc(d, window_sec=args.window, model=model)
            # --out 은 모델 비교용이다. 정식 산출물을 덮어쓰지 않고 index 도 건드리지 않는다.
            FT.save_json(Path(args.out) if args.out else REFINED_DIR / f'{d["id"]}.json', out)
            entry = next((m for m in index["meetings"] if m["id"] == d["id"]), None)
            if entry is not None and not args.out:
                entry["hasRefined"] = True
                entry["speakerTurns"] = out["speakerTurns"]
                index["updatedAt"] = FT.now_iso()
                FT.save_json(FT.INDEX_PATH, index)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f'::warning::{d["id"]} 교정 실패: {exc}')

    print(f"\n완료 · 성공 {len(docs) - failures} / 실패 {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
