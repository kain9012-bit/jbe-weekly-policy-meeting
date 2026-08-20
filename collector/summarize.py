"""자막을 회의 구조 데이터로 변환한다 (Gemini / OpenAI 전환 가능).

설계 원칙: **모든 요약 항목에 원문 인용과 타임스탬프를 붙인다.**
자동자막 기반이라 오류가 섞일 수밖에 없으므로, 읽는 사람이 바로 영상의 해당
지점으로 넘어가 확인할 수 있어야 한다.
"""
from __future__ import annotations

import json
import re

from config import (GEMINI_API_KEY, LLM_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL,
                    SUMMARY_MODEL)
from correct import departments

SCHEMA_HINT = """
{
  "summary": "회의 전체를 5~7문장으로. 무엇이 보고되고 무엇이 지시되었는지 중심으로.",
  "highlights": ["한 줄짜리 핵심 3~6개"],
  "agenda": [
    {"seq": 1, "dept": "부서명", "topic": "안건명", "gist": "2~4문장 요약", "t": 137}
  ],
  "directives": [
    {"dept": "부서명", "text": "지시 내용을 한 문장 명령형으로", "quote": "자막 원문 그대로 한 문장",
     "t": 380, "type": "지시|당부|질의", "due": "기한 언급이 있으면 그대로, 없으면 \\"\\""}
  ],
  "followups": [
    {"dept": "부서명", "matchedDirective": "지난주 지시사항 id 또는 \\"\\"",
     "report": "이번 회의에서 보고된 처리 결과", "quote": "회의록 원문", "t": 140,
     "progress": "완료|진행중|계획수립|미착수"}
  ]
}
""".strip()

PROMPT = """당신은 전북특별자치도교육청의 회의록 정리 담당자입니다.
아래는 매주 열리는 '주간정책회의'를 유튜브로 생중계한 영상의 회의록입니다.
자동생성 자막을 앞 단계에서 이미 문맥 교정하고 화자를 붙여 둔 것입니다
(`[분:초] 화자: 발언` 형태. 화자를 못 붙인 줄은 화자 없이 나옵니다).

## 회의 진행 방식 (고정된 패턴)
1. 교육감 인사말
2. 지난주 교육감 지시사항에 대한 **부서별 처리 결과 보고**
3. 부서별 **금주 주요 업무 보고**
4. 보고 중간중간 교육감의 질의와 **신규 지시·당부**
5. 마무리

## 반드시 지킬 것
- 교정을 거쳤지만 자동자막에서 온 것이라 여전히 틀린 낱말이 있을 수 있습니다.
  명백히 잘못된 표기는 바로잡아 쓰되, **내용을 추측해서 채우지는 마세요.**
- 부서는 화자 표시를 우선 믿되, 화자가 없는 줄은 문맥으로 판단하세요.
  **확신이 없으면 dept 를 비워 두세요. 지어내지 마세요.**
- directives 와 followups 의 quote 는 반드시 **회의록에 실제로 있는 문장**을 그대로 넣으세요.
  요약하거나 다듬지 마세요. 사람이 영상과 대조할 수 있어야 합니다.
- t 는 해당 발언이 시작되는 초 단위 시각입니다. 자막의 [분:초] 표기에서 계산하세요.
- 자막에 근거가 없는 내용은 절대 만들지 마세요. 해당 항목이 없으면 빈 배열로 두세요.

## 부서 후보군
{departments}

## 지난주 지시사항 (이번 회의의 처리 결과 보고와 연결할 것. 없으면 "없음")
{previous}

## 출력
아래 스키마의 JSON **하나만** 출력하세요. 설명·머리말·코드펜스 없이 JSON만.
{schema}

## 회의 정보
제목: {title}
일자: {date}

## 자막 전문
{transcript}
"""


def _render_previous(prev_meeting: dict | None) -> str:
    if not prev_meeting or not prev_meeting.get("directives"):
        return "없음"
    lines = []
    for d in prev_meeting["directives"]:
        lines.append(f'- [{d["id"]}] ({d.get("dept","")}) {d.get("text","")}')
    return "\n".join(lines)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM 응답에서 JSON을 찾지 못했습니다: {raw[:300]}")
    return json.loads(raw[start:end + 1])


def _call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 가 설정되지 않았습니다.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        res = client.models.generate_content(
            model=SUMMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=32768,
                # 함수 호출을 안 쓰는데 SDK 가 매번 경고를 찍어 로그를 어지럽힌다.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        from refine import model_error_hint
        raise RuntimeError(model_error_hint(exc, SUMMARY_MODEL)) from None
    return res.text


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    res = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return res.choices[0].message.content


def summarize(*, title: str, date: str, transcript: str,
              prev_meeting: dict | None = None) -> dict:
    prompt = PROMPT.format(
        departments=", ".join(departments()),
        previous=_render_previous(prev_meeting),
        schema=SCHEMA_HINT,
        title=title,
        date=date,
        transcript=transcript,
    )
    raw = _call_gemini(prompt) if LLM_PROVIDER == "gemini" else _call_openai(prompt)
    data = _extract_json(raw)

    # 최소한의 형태 보정. 교정·화자는 1.5단계(refine.py)가 맡으므로 여기서는 다루지 않는다.
    for key in ("highlights", "agenda", "directives", "followups"):
        data.setdefault(key, [])
        if not isinstance(data[key], list):
            data[key] = []
    data.setdefault("summary", "")
    return data


def model_name() -> str:
    return SUMMARY_MODEL if LLM_PROVIDER == "gemini" else OPENAI_MODEL
