"""1단계 · 영상 전체 스크립트 확보.

요약(LLM)과 완전히 분리된 단계다. 키가 없어도, 요약이 실패해도 이것만 돌리면
`data/transcripts/<회의ID>.json` 에 자막 전문이 쌓인다.

    python collector/fetch_transcripts.py                 # 아직 못 받은 회의만
    python collector/fetch_transcripts.py --all           # 전부 다시 받기
    python collector/fetch_transcripts.py --check         # 받지 않고 상태만 점검
    python collector/fetch_transcripts.py --video <ID>    # 게시판과 무관하게 영상 하나만
    python collector/fetch_transcripts.py --video <ID> --srt out.srt

`--check` 는 게시판·영상 목록과 이미 확보한 자막을 대조해 표로 보여준다.
설치 직후 "지금 뭐가 되고 뭐가 안 되는지" 를 확인하는 용도다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board  # noqa: E402
import captions  # noqa: E402
from config import INDEX_PATH, TRANSCRIPTS_DIR  # noqa: E402
from correct import correct_cues  # noqa: E402


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"updatedAt": None, "seenPostIds": [], "meetings": []}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def transcript_path(meeting_id: str) -> Path:
    return TRANSCRIPTS_DIR / f"{meeting_id}.json"


def has_transcript(meeting_id: str) -> bool:
    return transcript_path(meeting_id).exists()


def hms(sec: int) -> str:
    return f"{sec // 60}분 {sec % 60}초" if sec < 3600 else f"{sec // 3600}시간 {sec % 3600 // 60}분"


def collect_targets(session=None) -> list[tuple[board.Post, str]]:
    """게시판에서 회의 게시글과 영상 ID를 모은다."""
    posts = [p for p in board.fetch_list(session) if board.is_meeting_post(p)]
    posts.sort(key=lambda p: p.date)
    out: list[tuple[board.Post, str]] = []
    for p in posts:
        vid = board.fetch_video_id(p, session)
        if vid:
            out.append((p, vid))
        else:
            print(f"  ! {p.title} — 게시글에서 영상을 찾지 못했습니다 (dataSid={p.post_id})")
    return out


def fetch_one(post: board.Post, video_id: str) -> dict:
    mid = board.meeting_id(post)
    print(f"  {mid} · {post.title}")
    tr = captions.fetch(video_id)
    cues, stats = correct_cues(tr.cues)
    doc = {
        "id": mid,
        "postId": post.post_id,
        "postUrl": post.url,
        "title": post.title,
        "date": post.date,
        "videoId": video_id,
        "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
        "durationSec": tr.duration_sec,
        "cueCount": len(cues),
        "charCount": sum(len(c["text"]) for c in cues),
        "source": tr.source,
        "fetchedAt": now_iso(),
        "glossaryHits": stats,
        "cues": cues,
    }
    print(f"    확보: 큐 {doc['cueCount']}개 · {doc['charCount']:,}자 · "
          f"{hms(doc['durationSec'])} · 교정 {sum(s['count'] for s in stats)}건")
    return doc


def upsert_index(index: dict, doc: dict) -> None:
    entry = next((m for m in index["meetings"] if m["id"] == doc["id"]), None)
    if entry is None:
        entry = {"id": doc["id"]}
        index["meetings"].append(entry)
    entry.update({
        "title": doc["title"], "date": doc["date"], "videoId": doc["videoId"],
        "postId": doc["postId"], "postUrl": doc["postUrl"],
        "durationSec": doc["durationSec"], "cueCount": doc["cueCount"],
        "charCount": doc["charCount"], "captionSource": doc["source"],
        "hasTranscript": True,
    })
    entry.setdefault("hasSummary", False)
    entry.setdefault("summary", "")
    entry.setdefault("directiveCount", 0)
    entry.setdefault("depts", [])
    index["meetings"].sort(key=lambda m: m.get("date", ""), reverse=True)
    if doc["postId"] not in index["seenPostIds"]:
        index["seenPostIds"].append(doc["postId"])
    index["updatedAt"] = now_iso()


def cmd_check() -> int:
    print("게시판·영상·자막 상태 점검\n")

    # 1) 도구부터. 이게 없으면 아래 결과가 전부 '없음' 으로 나와 영상 탓처럼 보인다.
    missing = captions.missing_dependencies()
    print("자막 추출 도구")
    for name in ("yt-dlp", "youtube-transcript-api"):
        print(f"  {name:<24} {'없음  ← 설치 필요' if name in missing else '설치됨'}")
    if missing:
        print(f"\n  pip install {' '.join(missing)}\n")
    else:
        print()

    targets = collect_targets()
    if not targets:
        print("회의 게시글을 찾지 못했습니다. 게시판 접근부터 확인하세요.")
        return 1

    from config import MEETINGS_DIR, REFINED_DIR

    print(f"{'회의ID':<10} {'날짜':<12} {'영상ID':<13} {'자막':<14} {'교정':<10} {'요약':<6} 제목")
    print("-" * 110)
    missing = unrefined = unsummarized = 0
    for post, vid in targets:
        mid = board.meeting_id(post)
        p = transcript_path(mid)
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            state = f"확보 ({d.get('cueCount', 0)}줄)"
        else:
            state, missing = "없음", missing + 1

        r = REFINED_DIR / f"{mid}.json"
        if r.exists():
            rd = json.loads(r.read_text(encoding="utf-8"))
            rstate = f"됨 (화자{rd.get('speakerTurns', 0)})"
        else:
            rstate, unrefined = "안 됨", unrefined + 1

        sstate = "됨" if (MEETINGS_DIR / f"{mid}.json").exists() else "안 됨"
        unsummarized += sstate == "안 됨"
        print(f"{mid:<10} {post.date:<12} {vid:<13} {state:<14} {rstate:<10} {sstate:<6} {post.title}")
    print("-" * 110)
    print(f"총 {len(targets)}회차 · 자막 미확보 {missing} · 교정 안 됨 {unrefined} · 요약 안 됨 {unsummarized}")
    return 0


def cmd_single(video_id: str, srt_path: str | None) -> int:
    print(f"영상 {video_id} 자막 요청")
    try:
        tr = captions.fetch(video_id)
    except captions.CaptionError as exc:
        # 스택 트레이스는 도움이 안 된다. 무엇을 하면 되는지만 보여준다.
        print(f"\n실패: {exc}")
        return 2
    cues, stats = correct_cues(tr.cues)
    print(f"확보: 큐 {len(cues)}개 · {sum(len(c['text']) for c in cues):,}자 · 경로 {tr.source}")
    if srt_path:
        Path(srt_path).write_text(captions.as_srt(cues), encoding="utf-8")
        print(f"SRT 저장: {srt_path}")
    else:
        for c in cues[:20]:
            print(f"  [{c['t'] // 60}:{c['t'] % 60:02d}] {c['text']}")
        if len(cues) > 20:
            print(f"  … 이하 {len(cues) - 20}개 생략 (--srt 로 전체 저장)")
    print(f"교정 {sum(s['count'] for s in stats)}건: "
          + ", ".join(s["rule"] for s in stats[:5]) if stats else "교정 없음")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="주간정책회의 영상 자막 확보 (1단계)")
    ap.add_argument("--all", action="store_true", help="이미 받은 회차도 다시 받기")
    ap.add_argument("--check", action="store_true", help="받지 않고 상태만 점검")
    ap.add_argument("--video", help="게시판과 무관하게 영상 ID 하나만 처리")
    ap.add_argument("--srt", help="--video 와 함께 쓰면 SRT 파일로 저장")
    args = ap.parse_args()

    if args.video:
        return cmd_single(args.video, args.srt)
    if args.check:
        return cmd_check()

    # 도구가 하나도 없으면 회차마다 같은 실패를 4번 찍는 대신 여기서 끊는다.
    if len(captions.missing_dependencies()) == 2:
        print(f"::error::{captions.INSTALL_HINT}")
        return 2

    index = load_index()
    targets = collect_targets()
    todo = [(p, v) for p, v in targets if args.all or not has_transcript(board.meeting_id(p))]
    print(f"회의 {len(targets)}회차 · 이번에 받을 회차 {len(todo)}개")
    if not todo:
        print("새로 받을 자막이 없습니다.")
        return 0

    failures = 0
    for post, vid in todo:
        try:
            doc = fetch_one(post, vid)
            save_json(transcript_path(doc["id"]), doc)
            upsert_index(index, doc)
            save_json(INDEX_PATH, index)
        except captions.BotBlocked as exc:
            # IP 차단은 회차 문제가 아니라 실행 위치 문제다. 나머지도 다 실패하므로 멈춘다.
            print(f"::error::{exc}")
            return 2
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"::warning::{post.title} 자막 실패: {exc}")

    print(f"\n완료 · 성공 {len(todo) - failures} / 실패 {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
