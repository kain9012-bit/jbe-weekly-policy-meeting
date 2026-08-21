"""회의 영상의 오디오만 내려받는다.

    python collector/fetch_audio.py            # 아직 없는 회차만
    python collector/fetch_audio.py --all
    python collector/fetch_audio.py --id 2026-W34

## 왜 오디오가 필요한가
유튜브 자동자막은 고유명사에 약하다. '누리집'을 '무리집', '재무과'를 '제목과',
'청렴시스템'을 '청 시스템'으로 듣는다. 사전으로 하나씩 고치고 있지만 끝이 없다.
원본 오디오를 직접 받아쓰면(whisper) 이런 오류가 애초에 훨씬 적고,
목소리로 화자를 갈라낼 수도 있다.

## 왜 이걸 노트북에서 돌려야 하나
유튜브는 데이터센터 IP를 막는다. 클라우드에서 받으면
`HTTP 429` / `Sign in to confirm you're not a bot` 이 뜬다. 국내 가정·사무실
회선에서는 그냥 된다. 그래서 이 스크립트는 **내 노트북에서** 돌린다.

## ffmpeg 없이 받는다
`-x --audio-format mp3` 같은 변환은 ffmpeg 를 요구한다. 여기서는 변환하지 않고
유튜브가 주는 오디오 스트림(m4a/webm)을 그대로 받는다. 받아쓰기는 어차피
클라우드에서 하고, 거기에는 ffmpeg 가 있다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, INDEX_PATH  # noqa: E402

AUDIO_DIR = DATA_DIR / "audio"

#: 음성만 필요하므로 화질 좋은 트랙을 받을 이유가 없다.
#: 70kbps 이하를 먼저 고르면 1시간 회의가 30MB 안쪽으로 떨어진다.
FORMAT = "bestaudio[abr<=70]/bestaudio[abr<=100]/bestaudio"


def have_ytdlp() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       capture_output=True, check=True)
        return True
    except Exception:
        return False


def download(video_id: str, out_stem: Path) -> Path | None:
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", FORMAT,
        "--no-playlist",
        "--no-part",
        "-o", f"{out_stem}.%(ext)s",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    print("   내려받는 중… (몇 분 걸릴 수 있습니다)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        print("   실패:")
        for line in tail:
            print("     ", line)
        return None
    found = sorted(out_stem.parent.glob(f"{out_stem.name}.*"))
    return found[0] if found else None


def main() -> int:
    ap = argparse.ArgumentParser(description="회의 오디오 내려받기")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", help="회차 (예: 2026-W34)")
    args = ap.parse_args()

    if not have_ytdlp():
        print("yt-dlp 가 없습니다.  pip install yt-dlp")
        return 1
    if not INDEX_PATH.exists():
        print("data/index.json 이 없습니다. 먼저 자막을 수집하세요.")
        return 1

    meetings = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["meetings"]
    if args.id:
        meetings = [m for m in meetings if m["id"] == args.id]
    elif not args.all:
        meetings = [m for m in meetings
                    if not list(AUDIO_DIR.glob(f"{m['id']}.*"))]

    if not meetings:
        print("받을 대상이 없습니다. (--all 로 전부 다시 받을 수 있습니다)")
        return 0

    ok = 0
    for m in meetings:
        print(f"\n{m['id']} · {m['title']}")
        existing = list(AUDIO_DIR.glob(f"{m['id']}.*"))
        if existing and not (args.all or args.id):
            print(f"   이미 있음: {existing[0].name}")
            continue
        path = download(m["videoId"], AUDIO_DIR / m["id"])
        if path:
            mb = path.stat().st_size / 1024 / 1024
            print(f"   완료: {path.name}  ({mb:.1f} MB)")
            ok += 1

    print(f"\n{ok}개 받았습니다 → {AUDIO_DIR}")
    return 0 if ok or not meetings else 1


if __name__ == "__main__":
    raise SystemExit(main())
