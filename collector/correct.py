"""자동자막(ASR) 오인식 후보정.

유튜브 자동자막은 고유명사에 특히 약하다. 실제 확인된 사례:
    "주관 정책일"   -> "주간정책회의"
    "청년 콘텐츠 공무전" -> "청렴 콘텐츠 공모전"
    "노사 협력가"   -> "노사협력과"
사전 기반으로 먼저 고치고, LLM 단계에서 문맥으로 한 번 더 다듬는다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from config import GLOSSARY_PATH


@lru_cache(maxsize=1)
def load_glossary() -> dict:
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[re.Pattern, str]]:
    return [
        (re.compile(r["pattern"]), r["to"])
        for r in load_glossary().get("replacements", [])
    ]


def correct_text(text: str) -> tuple[str, dict[str, int]]:
    """문자열 하나를 교정하고, 어떤 치환이 몇 번 일어났는지 함께 돌려준다."""
    hits: dict[str, int] = {}
    for pat, to in _compiled():
        text, n = pat.subn(to, text)
        if n:
            hits[f"{pat.pattern} -> {to}"] = hits.get(f"{pat.pattern} -> {to}", 0) + n
    return text, hits


def correct_cues(cues: list[dict]) -> tuple[list[dict], list[dict]]:
    """자막 큐 목록 전체를 교정한다.

    cues: [{"t": 12, "text": "..."}]
    반환: (교정된 큐, 치환 통계)
    """
    total: dict[str, int] = {}
    out: list[dict] = []
    for cue in cues:
        fixed, hits = correct_text(cue["text"])
        item = {"t": cue["t"], "text": fixed}
        if fixed != cue["text"]:
            item["raw"] = cue["text"]
        for k, v in hits.items():
            total[k] = total.get(k, 0) + v
        out.append(item)
    stats = [
        {"rule": k, "count": v}
        for k, v in sorted(total.items(), key=lambda kv: -kv[1])
    ]
    return out, stats


def departments() -> list[str]:
    return load_glossary().get("departments", [])
