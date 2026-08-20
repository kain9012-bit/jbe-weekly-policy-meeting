"""전체 파이프라인 = 1단계(자막) → 1.5단계(교정·화자) → 2단계(요약).

    python collector/run.py                   # 신규 회차를 끝까지
    python collector/run.py --all             # 전 회차 다시
    python collector/run.py --transcripts-only   # 자막까지만
    python collector/run.py --refine-only        # 교정·화자만
    python collector/run.py --summary-only       # 요약만
    python collector/run.py --skip-refine        # 교정 건너뛰고 사전 교정본으로 요약

앞 단계가 실패하면 뒤 단계는 시도하지 않는다. 자막 없이 만든 요약은 의미가 없다.
단계별 산출물이 따로 저장되므로 어느 하나가 실패해도 앞의 결과는 남는다.
    data/transcripts/  1단계 · 자막 원문 + 사전 교정
    data/refined/      1.5단계 · 문맥 교정 + 화자
    data/meetings/     2단계 · 요약
"""
from __future__ import annotations

import argparse
import os
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board  # noqa: E402
import captions  # noqa: E402
import fetch_transcripts as FT  # noqa: E402
import refine as RF  # noqa: E402
from config import INDEX_PATH, MEETINGS_DIR, REFINED_DIR, SKIP_SUMMARY  # noqa: E402


def meeting_path(mid: str) -> Path:
    return MEETINGS_DIR / f"{mid}.json"


def previous_meeting(index: dict, before_date: str) -> dict | None:
    earlier = [m for m in index["meetings"]
               if m.get("date", "") < before_date and m.get("hasSummary")]
    if not earlier:
        return None
    prev = max(earlier, key=lambda m: m["date"])
    p = meeting_path(prev["id"])
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def summarize_one(mid: str, index: dict) -> dict:
    import summarize as S

    doc, is_refined = RF.load_best(mid)
    cues = doc["cues"]
    body = RF.plain_text(cues) if is_refined else captions.plain_text(cues)
    print(f"  {mid} 요약 생성 중… ({'교정본' if is_refined else '사전 교정본'}, "
          f"{sum(len(c['text']) for c in cues):,}자)")

    result = S.summarize(title=doc["title"], date=doc["date"], transcript=body,
                         prev_meeting=previous_meeting(index, doc["date"]))

    meeting = {
        "id": mid,
        "postId": doc["postId"], "postUrl": doc["postUrl"],
        "title": doc["title"], "date": doc["date"],
        "videoId": doc["videoId"], "videoUrl": doc["videoUrl"],
        "durationSec": doc["durationSec"],
        "summary": result.get("summary", ""),
        "highlights": result.get("highlights", []),
        "agenda": result.get("agenda", []),
        "directives": [{**d, "id": f"{mid}-D{i + 1}"}
                       for i, d in enumerate(result.get("directives", []))],
        "followups": result.get("followups", []),
        # 교정 내역은 LLM 자기 보고가 아니라 실제 차이에서 뽑는다.
        "corrections": RF.corrections_from(cues)[:40],
        "meta": {
            "captionSource": doc.get("source", ""),
            "refined": is_refined,
            "refineModel": doc.get("refineModel"),
            "llm": S.model_name(),
            "summarizedAt": FT.now_iso(),
        },
    }
    print(f"    안건 {len(meeting['agenda'])} · 지시 {len(meeting['directives'])} "
          f"· 처리결과 {len(meeting['followups'])}")
    return meeting


def upsert_summary_index(index: dict, meeting: dict) -> None:
    entry = next((m for m in index["meetings"] if m["id"] == meeting["id"]), None)
    if entry is None:
        entry = {"id": meeting["id"]}
        index["meetings"].append(entry)
    entry.update({
        "hasSummary": True,
        "summary": meeting["summary"],
        "directiveCount": len(meeting["directives"]),
        "depts": sorted({d.get("dept", "") for d in meeting["directives"] if d.get("dept")}),
    })
    index["updatedAt"] = FT.now_iso()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--post", help="특정 dataSid만")
    ap.add_argument("--dry-run", action="store_true", help="신규 여부만 확인")
    ap.add_argument("--transcripts-only", action="store_true")
    ap.add_argument("--refine-only", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--skip-refine", action="store_true", help="교정 없이 사전 교정본으로 요약")
    args = ap.parse_args()

    only = args.transcripts_only or args.refine_only or args.summary_only
    do_fetch = not only or args.transcripts_only
    do_refine = (not only or args.refine_only) and not args.skip_refine
    do_summary = (not only or args.summary_only) and not SKIP_SUMMARY

    index = FT.load_index()

    # ── 1단계 · 자막 ─────────────────────────────────────────────
    if do_fetch:
        if len(captions.missing_dependencies()) == 2:
            print(f"::error::{captions.INSTALL_HINT}")
            return 2

        targets = FT.collect_targets()
        if args.post:
            targets = [(p, v) for p, v in targets if p.post_id == args.post]
        todo = [(p, v) for p, v in targets
                if args.all or not FT.has_transcript(board.meeting_id(p))]

        print(f"[1단계] 회의 {len(targets)}회차 · 자막 받을 회차 {len(todo)}개")
        if args.dry_run:
            print(f"::notice::자막 미확보 {len(todo)}회차")
            return 0

        for post, vid in todo:
            try:
                doc = FT.fetch_one(post, vid)
                FT.save_json(FT.transcript_path(doc["id"]), doc)
                FT.upsert_index(index, doc)
                FT.save_json(INDEX_PATH, index)
            except captions.BotBlocked as exc:
                print(f"::error::{exc}")
                return 2
            except Exception as exc:  # noqa: BLE001
                print(f"::warning::{post.title} 자막 실패: {exc}")

    if args.transcripts_only:
        print("자막 단계까지만 수행했습니다.")
        return 0

    ids = [m["id"] for m in sorted(index["meetings"], key=lambda m: m.get("date", ""))
           if m.get("hasTranscript")]

    # ── 1.5단계 · 교정 + 화자 ────────────────────────────────────
    if do_refine:
        pending = [i for i in ids if args.all or not (REFINED_DIR / f"{i}.json").exists()]
        print(f"\n[1.5단계] 자막 확보 {len(ids)}회차 · 교정할 회차 {len(pending)}개")
        for mid in pending:
            try:
                tr = json.loads(FT.transcript_path(mid).read_text(encoding="utf-8"))
                out = RF.refine_doc(tr, window_sec=RF.REFINE_WINDOW_SEC)
                FT.save_json(REFINED_DIR / f"{mid}.json", out)
                entry = next((m for m in index["meetings"] if m["id"] == mid), None)
                if entry is not None:
                    entry["hasRefined"] = True
                    entry["speakerTurns"] = out["speakerTurns"]
                    index["updatedAt"] = FT.now_iso()
                    FT.save_json(INDEX_PATH, index)
            except Exception as exc:  # noqa: BLE001
                print(f"::warning::{mid} 교정 실패: {exc}")

    if args.refine_only:
        return 0

    # ── 2단계 · 요약 ─────────────────────────────────────────────
    if not do_summary:
        print("요약 단계는 건너뛰었습니다 (SKIP_SUMMARY).")
        return 0

    pending = [i for i in ids if args.all or not meeting_path(i).exists()]
    print(f"\n[2단계] 요약할 회차 {len(pending)}개")

    failures = 0
    for mid in pending:
        try:
            meeting = summarize_one(mid, index)
            FT.save_json(meeting_path(mid), meeting)
            upsert_summary_index(index, meeting)
            FT.save_json(INDEX_PATH, index)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            # 스택 트레이스는 회차마다 수십 줄씩 찍혀 정작 원인을 가린다.
            # 무엇이 왜 실패했는지만 보여주고, 자세한 건 DEBUG=1 일 때만 남긴다.
            print(f"::warning::{mid} 요약 실패: {exc}")
            if os.getenv("DEBUG"):
                traceback.print_exc()

    print(f"\n완료 · 요약 성공 {len(pending) - failures} / 실패 {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
