"""정리한 회차를 저장·발행하기 전에 거는 검증.

    python scripts/verify.py                 # 저장소 루트에서
    python scripts/verify.py --id 2026-W35   # 한 회차만

사람이 판단한 것 중 **기계가 확인할 수 있는 것은 전부 기계가 확인한다.**
회차마다 사람이 달라지고 컨디션이 달라져도, 여기서 걸리는 종류의 실수는 나가지 않는다.

실제로 이 검사들은 전부 한 번씩 실패했던 것들이다:
  · 인용문이 회의록에 없음      → 요약을 쓰면서 문장을 다듬다가 원문과 어긋남
  · 지시-보고 연결이 비어 있음  → 최신 회차부터 정리해서 연결할 대상이 없었음
  · 부서명이 기구도에 없음      → '학생생활과' 처럼 없는 과를 지어냄
  · 부서가 빈 지시             → 필터에 안 걸려서 검색해도 안 나옴
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "data").exists():
    ROOT = Path.cwd()

DATA = ROOT / "data"
COLLECTIVE = {"전 부서", "모든 기관", "교육지원청", "직속기관", "부서 미상"}


def split_depts(v: str | None) -> list[str]:
    return [x.strip() for x in re.split(r"[/,·]", v or "") if x.strip()]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def check(meeting_ids: list[str]) -> int:
    glossary = load(ROOT / "collector" / "glossary.json")
    known = set(glossary.get("departments", [])) | COLLECTIVE | {"교육감"}

    meetings = {}
    for mid in meeting_ids:
        meetings[mid] = load(DATA / "meetings" / f"{mid}.json")
    order = sorted(meetings, key=lambda k: meetings[k]["date"])
    all_directives = {d["id"]: (mid, d)
                      for mid, m in meetings.items() for d in m["directives"]}

    fails: list[str] = []
    for mid in order:
        m = meetings[mid]
        refined = DATA / "refined" / f"{mid}.json"
        if not refined.exists():
            fails.append(f"{mid}: 회의록(refined)이 없다")
            continue
        r = load(refined)
        full = " ".join(c["text"] for c in r["cues"])

        # 1. 인용문은 회의록에 글자 그대로 있어야 한다
        for d in m["directives"]:
            if d.get("quote") and d["quote"] not in full:
                fails.append(f"{mid} {d['id']}: 인용문이 회의록에 없다 — {d['quote'][:40]}…")
        for i, f in enumerate(m["followups"]):
            if f.get("quote") and f["quote"] not in full:
                fails.append(f"{mid} 보고[{i}]: 인용문이 회의록에 없다 — {f['quote'][:40]}…")

        # 2. 부서는 기구도에 있는 이름이어야 하고, 비어 있으면 안 된다
        for d in m["directives"]:
            names = split_depts(d.get("dept"))
            if not names:
                fails.append(f"{mid} {d['id']}: 부서가 비어 있다 (필터에 안 걸린다)")
            for n in names:
                if n not in known:
                    fails.append(f"{mid} {d['id']}: 기구도에 없는 부서 '{n}'")

        # 3. 처리 결과는 **더 앞선 회차의** 지시를 가리켜야 한다
        for i, f in enumerate(m["followups"]):
            did = f.get("matchedDirective") or ""
            if not did:
                continue
            if did not in all_directives:
                fails.append(f"{mid} 보고[{i}]: 존재하지 않는 지시 {did}")
                continue
            src, _ = all_directives[did]
            if meetings[src]["date"] >= m["date"]:
                fails.append(f"{mid} 보고[{i}]: {did} 는 더 앞선 회차의 지시가 아니다")

        # 4. 화자는 다 채워져야 한다
        heads = [c for c in r["cues"] if c.get("turnStart")]
        blank = [h for h in heads if not h.get("speaker")]
        if blank:
            fails.append(f"{mid}: 화자가 빈 발언 {len(blank)}개 "
                         f"(첫 자리 {int(blank[0]['t'])//60}:{int(blank[0]['t'])%60:02d})")

        print(f"  {mid}  발언 {len(heads):>3} · 화자 {len(heads)-len(blank):>3} · "
              f"지시 {len(m['directives']):>2} · 보고 {len(m['followups'])} "
              f"(연결 {sum(1 for f in m['followups'] if f.get('matchedDirective'))})")

    # 5. 이번에 새로 정리한 회차의 보고가 하나도 연결되지 않았다면 의심한다
    last = order[-1]
    fu = meetings[last]["followups"]
    if fu and not any(f.get("matchedDirective") for f in fu):
        fails.append(f"{last}: 처리 결과 {len(fu)}건이 전부 연결되지 않았다 — "
                     f"이전 회차 지시를 펼쳐 놓고 다시 확인할 것")

    print()
    if fails:
        print(f"✗ {len(fails)}건 걸렸습니다. 고치기 전에는 발행하지 마세요.\n")
        for f in fails:
            print("   ·", f)
        return 1
    print("✓ 전부 통과했습니다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="회차 검증")
    ap.add_argument("--id", help="한 회차만 (지정해도 연결 검사를 위해 전 회차를 읽는다)")
    args = ap.parse_args()
    ids = sorted(p.stem for p in (DATA / "meetings").glob("*.json"))
    if not ids:
        print("정리된 회차가 없습니다.")
        return 1
    if args.id and args.id not in ids:
        print(f"{args.id} 회차가 없습니다.")
        return 1
    return check(ids)


if __name__ == "__main__":
    raise SystemExit(main())
