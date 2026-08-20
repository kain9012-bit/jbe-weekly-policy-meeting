"""유튜브 자막 추출 — 이 프로젝트의 1단계이자 가장 중요한 부분.

요약(LLM)은 자막이 있어야 시작할 수 있다. 그래서 자막 확보는 요약과 분리해
`fetch_transcripts.py` 로 단독 실행·검증할 수 있게 해 두었다.

추출 경로를 순서대로 시도한다.
    1) yt-dlp · json3   — 시각 정보가 가장 정확하다
    2) yt-dlp · vtt     — json3 를 못 받을 때
    3) youtube-transcript-api — yt-dlp 가 막혔을 때의 마지막 시도

전제: **자체 호스팅 러너(사무실 PC, 국내 IP)** 에서 실행한다.
클라우드/데이터센터 IP에서는 유튜브가 `Sign in to confirm you're not a bot` 으로
막는 것이 2026-08 실측으로 확인되었다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import CAPTION_LANG, YTDLP_COOKIES, YTDLP_TIMEOUT


class CaptionError(RuntimeError):
    """자막을 끝내 못 받았을 때. 메시지에 원인과 다음 조치를 담는다."""


class BotBlocked(CaptionError):
    """데이터센터 IP 차단. 러너 위치를 바꿔야 한다."""


class MissingDependency(CaptionError):
    """yt-dlp 도 youtube-transcript-api 도 없다. 영상 문제가 아니라 설치 문제."""


BOT_HINTS = ("confirm you", "not a bot", "Sign in to confirm")
NO_SUB_HINTS = ("There are no subtitles", "no automatic captions")


@dataclass
class Transcript:
    video_id: str
    cues: list[dict]          # [{"t": 초, "text": "..."}]
    source: str               # 어떤 경로로 받았는지
    duration_sec: int

    @property
    def char_count(self) -> int:
        return sum(len(c["text"]) for c in self.cues)


# ────────────────────────────── yt-dlp ──────────────────────────────

def _ytdlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def _run_ytdlp(video_id: str, sub_format: str, workdir: Path) -> Path | None:
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs", f"{CAPTION_LANG},{CAPTION_LANG}-orig,{CAPTION_LANG}.*",
        "--sub-format", sub_format,
        "--no-warnings",
        "--retries", "3",
        "-o", str(workdir / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    if YTDLP_COOKIES and Path(YTDLP_COOKIES).exists():
        cmd[1:1] = ["--cookies", YTDLP_COOKIES]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=YTDLP_TIMEOUT)
    blob = (proc.stdout or "") + (proc.stderr or "")
    if any(h in blob for h in BOT_HINTS):
        raise BotBlocked(
            "유튜브가 봇으로 판단해 요청을 거부했습니다.\n"
            "  → 이 작업은 자체 호스팅 러너(국내 IP)에서 실행해야 합니다.\n"
            "  → 클라우드에서 꼭 돌려야 한다면 YTDLP_COOKIES_FILE 을 설정하세요.\n"
            f"--- yt-dlp 출력 ---\n{blob[-1200:]}"
        )
    found = sorted(workdir.glob(f"*{CAPTION_LANG}*.{sub_format}"))
    return found[0] if found else None


def _parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cues: list[dict] = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = re.sub(r"\s+", " ", "".join(s.get("utf8", "") for s in segs)).strip()
        if not text:
            continue
        cues.append({"t": int(ev.get("tStartMs", 0)) // 1000, "text": text})
    return cues


VTT_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})\.(\d{3})\s+-->")


def _parse_vtt(text: str) -> list[dict]:
    cues: list[dict] = []
    cur: int | None = None
    buf: list[str] = []

    def flush():
        if cur is not None and buf:
            line = " ".join(buf).strip()
            if line:
                cues.append({"t": cur, "text": line})

    for raw in text.splitlines():
        m = VTT_TS.search(raw)
        if m:
            flush()
            h, mi, s, _ = m.groups()
            cur = int(h or 0) * 3600 + int(mi) * 60 + int(s)
            buf = []
            continue
        # 자동자막은 낱말마다 <00:00:13.500><c>…</c> 같은 태그를 끼워 넣는다.
        # 태그를 지우면 공백이 겹치므로, 겹침 판정 전에 공백을 하나로 모은다.
        line = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", raw)).strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            continue
        if re.fullmatch(r"\d+", line):        # 큐 번호
            continue
        buf.append(line)
    flush()

    # 자동자막 vtt 는 한 문장을 조금씩 늘려가며 여러 번 내보낸다(rolling caption).
    # 앞 큐가 뒤 큐에 포함되면 문장은 긴 쪽을 쓰되 **시각은 처음 나온 때**를 지킨다.
    out: list[dict] = []
    for c in cues:
        if out and (c["text"] == out[-1]["text"] or c["text"] in out[-1]["text"]):
            continue
        if out and out[-1]["text"] in c["text"]:
            out[-1] = {"t": out[-1]["t"], "text": c["text"]}
            continue
        out.append(c)
    return out


# ─────────────────────── youtube-transcript-api ───────────────────────

def _transcript_api_available() -> bool:
    try:
        import youtube_transcript_api  # noqa: F401
        return True
    except ImportError:
        return False


def _via_transcript_api(video_id: str) -> list[dict]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return []
    try:
        raw = YouTubeTranscriptApi().fetch(video_id, languages=[CAPTION_LANG]).to_raw_data()
    except Exception:                          # noqa: BLE001 — 이 경로는 실패해도 다음으로 넘어간다
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=[CAPTION_LANG])
        except Exception:                      # noqa: BLE001
            return []
    return [
        {"t": int(r.get("start", 0)), "text": str(r.get("text", "")).replace("\n", " ").strip()}
        for r in raw
        if str(r.get("text", "")).strip()
    ]


# ────────────────────────────── 공개 함수 ──────────────────────────────

def missing_dependencies() -> list[str]:
    """설치되지 않은 자막 추출 도구 이름."""
    missing = []
    if not _ytdlp_available():
        missing.append("yt-dlp")
    if not _transcript_api_available():
        missing.append("youtube-transcript-api")
    return missing


INSTALL_HINT = (
    "자막 추출 도구가 설치되어 있지 않습니다.\n"
    "  → pip install yt-dlp youtube-transcript-api\n"
    "  (pip install -r collector/requirements.txt 가 UnicodeDecodeError 로 실패한다면 "
    "위 명령으로 직접 설치하세요.)"
)


def fetch(video_id: str, *, verbose: bool = True) -> Transcript:
    """자막을 받아 Transcript 로 돌려준다. 실패하면 CaptionError."""
    attempts: list[str] = []

    def say(msg: str) -> None:
        if verbose:
            print(f"    {msg}")

    # 도구가 하나도 없으면 영상 탓이 아니다. 헷갈리지 않게 먼저 끊는다.
    if missing_dependencies() == ["yt-dlp", "youtube-transcript-api"]:
        raise MissingDependency(INSTALL_HINT)

    if _ytdlp_available():
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            for fmt, parse in (("json3", lambda p: _parse_json3(p)),
                               ("vtt", lambda p: _parse_vtt(p.read_text(encoding="utf-8")))):
                try:
                    path = _run_ytdlp(video_id, fmt, workdir)
                except BotBlocked:
                    raise
                except subprocess.TimeoutExpired:
                    attempts.append(f"yt-dlp/{fmt}: 시간 초과")
                    say(f"yt-dlp {fmt} — 시간 초과")
                    continue
                if not path:
                    attempts.append(f"yt-dlp/{fmt}: 자막 파일 없음")
                    say(f"yt-dlp {fmt} — 자막 파일 없음")
                    continue
                cues = parse(path)
                if cues:
                    say(f"yt-dlp {fmt} — 큐 {len(cues)}개")
                    return Transcript(video_id, cues, f"yt-dlp/{fmt}", cues[-1]["t"])
                attempts.append(f"yt-dlp/{fmt}: 파싱 결과 0건")
    else:
        attempts.append("yt-dlp 미설치")
        say("yt-dlp 가 설치되어 있지 않습니다 (pip install yt-dlp)")

    if _transcript_api_available():
        cues = _via_transcript_api(video_id)
        if cues:
            say(f"youtube-transcript-api — 큐 {len(cues)}개")
            return Transcript(video_id, cues, "youtube-transcript-api", cues[-1]["t"])
        attempts.append("youtube-transcript-api: 자막 없음")
    else:
        attempts.append("youtube-transcript-api 미설치")
        say("youtube-transcript-api 가 설치되어 있지 않습니다")

    missing = missing_dependencies()
    tail = (
        f"  {', '.join(missing)} 이(가) 설치되어 있지 않습니다. "
        "pip install yt-dlp youtube-transcript-api"
        if missing
        else "  업로드 직후에는 자동자막 생성이 끝나지 않았을 수 있습니다. 다음 실행에서 재시도합니다."
    )
    raise CaptionError(
        f"영상 {video_id} 의 '{CAPTION_LANG}' 자막을 받지 못했습니다.\n"
        "  시도한 경로: " + " / ".join(attempts) + "\n" + tail
    )


def plain_text(cues: list[dict]) -> str:
    """LLM 입력용 — 타임스탬프를 붙인 평문."""
    return "\n".join(f"[{c['t'] // 60}:{c['t'] % 60:02d}] {c['text']}" for c in cues)


def as_srt(cues: list[dict]) -> str:
    """사람이 읽거나 다른 도구에 넘기기 좋은 SRT."""
    def stamp(sec: int) -> str:
        return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d},000"

    out: list[str] = []
    for i, c in enumerate(cues, 1):
        end = cues[i]["t"] if i < len(cues) else c["t"] + 5
        out += [str(i), f"{stamp(c['t'])} --> {stamp(max(end, c['t'] + 1))}", c["text"], ""]
    return "\n".join(out)
