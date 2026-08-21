"""오디오에서 직접 받아쓰고, 목소리로 화자를 갈라내고, 유튜브 자막과 대조한다.

    python collector/transcribe.py --id 2026-W34
    python collector/transcribe.py --id 2026-W34 --resume    # 받아쓰기는 건너뛰고 다시 정리만
    python collector/transcribe.py --id 2026-W34 --no-diarize

산출물: `data/asr/<회차>.json`

## 왜 유튜브 자막 대신 오디오를 쓰나
유튜브 자동자막은 고유명사에 약하다. '누리집'→'무리집', '재무과'→'제목과',
'청렴시스템'→'청 시스템'. 사전으로 하나씩 고치는 건 끝이 없다. 원본 오디오를
whisper 로 받아쓰면 이 오류가 크게 줄고, 무엇보다 **목소리로 화자를 가를 수 있다.**

## 그런데 왜 자막도 계속 받나
받아쓰기와 자막은 **서로 다른 것을 놓친다.**

- whisper 는 가끔 30초짜리 발언을 "네, 다음 부서로 가겠습니다." 한 줄로 뭉갠다.
  오류가 아니라 그냥 짧게 나오기 때문에 결과만 보면 알아챌 수 없다.
  W34 에서 실제로 3군데 102초가 이렇게 사라졌고, 그중 하나가 정책기획과의
  공약사업 실천계획 보고 **전체**였다.
- 유튜브 자막은 2~3초마다 끊기고 고유명사를 자주 틀리지만, **빠뜨리지는 않는다.**

그래서 자막을 정답지가 아니라 **대조본**으로 쓴다. 같은 30초 동안 자막은 200자를
담았는데 받아쓴 결과가 16자라면, 그건 조용한 구간이 아니라 놓친 구간이다.
이 판단은 추측이 아니라 증거다. 찾아낸 구간은 침묵제거를 끄고 다시 받아쓰고,
그래도 안 나오면(마이크에서 먼 발언) 자막의 그 구간을 대신 쓰고 그렇게 표시한다.

## 화자 분리를 왜 직접 짜나
표준 도구인 pyannote 의 사전학습 모델은 전부 HuggingFace 의 gated 저장소라
계정·약관 동의·토큰이 필요하다. 토큰을 주고받지 않으려고, 토큰 없이 받을 수 있는
speechbrain ECAPA 화자 임베딩 + 군집화로 같은 일을 한다. 이 회의처럼 화자가
또렷이 번갈아 말하는 구조에서는 충분하다 (W34 실루엣 0.513, 14개 군집).

## 이름은 사람이 붙인다
군집이 알려 주는 건 '이 구간과 저 구간은 같은 사람'까지다. 누구인지는
"○○과 말씀드리겠습니다" 가 들어 있는 군집을 보고 정하고, 나머지는
`data/human/<회차>.json` 에 사람이 적는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, TRANSCRIPTS_DIR  # noqa: E402

AUDIO_DIR = DATA_DIR / "audio"
ASR_DIR = DATA_DIR / "asr"
SR = 16000


def find_audio(meeting_id: str) -> Path | None:
    hits = sorted(p for p in AUDIO_DIR.glob(f"{meeting_id}.*") if p.is_file())
    return hits[0] if hits else None


def load_captions(meeting_id: str) -> list[dict]:
    """대조에 쓸 유튜브 자막. 없으면 빈 목록."""
    p = TRANSCRIPTS_DIR / f"{meeting_id}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("cues", [])


def load_wave(path: Path):
    """오디오를 16kHz 모노 float32 로 읽는다 (ffmpeg 로 디코딩)."""
    import subprocess

    import numpy as np
    cmd = ["ffmpeg", "-nostdin", "-threads", "0", "-i", str(path),
           "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le", "-ar", str(SR), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.int16).astype("float32") / 32768.0


# ── 1) 받아쓰기 ────────────────────────────────────────────────────────────

def transcribe(path: Path, model_size: str, lang: str = "ko") -> list[dict]:
    from faster_whisper import WhisperModel

    print(f"   모델 준비: {model_size} (처음이면 내려받느라 몇 분 걸립니다)")
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=0)

    print("   받아쓰는 중…")
    t0 = time.time()
    segments, info = model.transcribe(
        str(path),
        language=lang,
        vad_filter=True,                      # 침묵 구간 제거 — 환각을 크게 줄인다
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
        condition_on_previous_text=False,     # 한 번 헛나가면 계속 끌고 가는 걸 막는다
    )
    out = []
    for s in segments:
        text = s.text.strip()
        if not text:
            continue
        out.append({"t": round(s.start, 2), "end": round(s.end, 2), "text": text})
        if len(out) % 25 == 0:
            done = s.end
            rate = done / max(time.time() - t0, 1e-9)
            left = max(info.duration - done, 0) / max(rate, 1e-9)
            print(f"     {int(done)//60}:{int(done)%60:02d} / "
                  f"{int(info.duration)//60}:{int(info.duration)%60:02d} "
                  f"· 남은 시간 약 {int(left)//60}분", flush=True)
    print(f"   받아쓰기 끝 · {len(out)}개 구간 · {time.time()-t0:.0f}초 걸림")
    return out


# ── 1.5) 자막과 대조해 삼켜진 구간 찾기·복구 ───────────────────────────────

#: 같은 시간대 자막 글자수의 몇 %에 못 미치면 삼킨 것으로 본다.
THIN_RATIO = 0.55
#: 자막이 이만큼은 담고 있어야 비교할 값어치가 있다.
MIN_CAP_CHARS = 30
#: 자막의 시각은 실제 발화보다 조금 늦게 찍힌다. 그 어긋남을 흡수하려고 여유를
#: 두면 오탐은 사라지지만 **진짜 누락도 같이 가려진다.** 실측(W34): 여유 0초는
#: 일부러 지운 4곳을 모두 잡아냈고, 2초만 줘도 절반을 놓쳤다.
#: 그래서 여유는 두지 않는다. 오탐은 비싸지 않다 — 그 30초를 다시 받아쓸 뿐이고,
#: 아래 1.5배 규칙이 '더 나아지지 않은 결과'로 바꿔치는 것을 막는다.
ASR_SLACK = 0.0
#: 자막이 없을 때만 쓰는 보조 기준. 한국어는 보통 초당 4~7자다.
LOW_DENSITY = 2.0
MIN_GAP_SEC = 8.0


def caption_text_in(caps: list[dict], a: float, b: float) -> str:
    """유튜브 자막에서 [a, b) 구간의 말을 모은다."""
    return " ".join(re.sub(r"^\s*>>\s*", "", c["text"]).strip()
                    for c in caps if a <= c["t"] < b).strip()


def asr_text_in(segs: list[dict], a: float, b: float) -> str:
    return " ".join(s["text"] for s in segs if a <= s["t"] < b).strip()


def find_thin_windows(segs: list[dict], caps: list[dict],
                      win: float = 30.0, step: float = 15.0) -> list[list[float]]:
    """자막과 대조해 '말이 있었는데 안 받아써진' 시간대를 찾는다.

    구간(segment) 단위로 비교하면 안 된다. whisper 가 어디서 끊었는지에 결과가
    좌우되기 때문이다. 실제로 같은 오디오를 두 번 돌렸더니 한 번은 35초짜리
    구간 하나로, 다른 한 번은 짧은 구간 여럿으로 쪼개져서 같은 누락이 한 번은
    잡히고 한 번은 안 잡혔다.

    그래서 **30초짜리 창을 15초씩 밀면서** 창 안의 글자수를 비교한다. 창은
    받아쓰기의 사정과 무관하므로 어떻게 쪼개지든 같은 답이 나온다.
    """
    if not caps or not segs:
        # 자막이 없으면(신규 회차) 글자 밀도로 대신 본다.
        return [[s["t"], s["end"]] for s in segs
                if (s["end"] - s["t"]) >= MIN_GAP_SEC
                and len(s["text"]) / max(s["end"] - s["t"], 1e-9) < LOW_DENSITY]

    end = max(s["end"] for s in segs)
    hits: list[list[float]] = []
    t = 0.0
    while t < end:
        a, b = t, min(t + win, end)
        cap = caption_text_in(caps, a, b)
        asr = asr_text_in(segs, a - ASR_SLACK, b + ASR_SLACK)
        # 자막도 비어 있으면 정말 조용한 구간이다.
        if len(cap) >= MIN_CAP_CHARS and len(asr) < len(cap) * THIN_RATIO:
            hits.append([a, b])
        t += step

    merged: list[list[float]] = []
    for a, b in hits:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def repair(path: Path, segs: list[dict], model_size: str,
           caps: list[dict], lang: str = "ko") -> tuple[int, int]:
    """삼켜진 구간을 다시 받아쓰고, 그래도 안 되면 자막으로 메운다."""
    from faster_whisper import WhisperModel

    windows = find_thin_windows(segs, caps)
    if not windows:
        print("   자막과 대조 — 빠뜨린 구간 없음")
        return 0, 0
    total = sum(b - a for a, b in windows)
    print(f"   자막과 대조 — 빠뜨린 것으로 보이는 시간대 {len(windows)}곳 "
          f"({int(total)}초), 다시 받아쓰는 중")

    wave = load_wave(path)
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=0)

    # 잘린 자리에서 바로 시작하면 첫 어절을 놓치고, 그 한 번의 미끄러짐이
    # 구간 전체를 망친다. 앞뒤로 조금 넉넉히 잘라서 넣는다.
    PAD = 2.0
    CONFIGS = [
        dict(beam_size=5),
        dict(beam_size=5, no_speech_threshold=0.9, log_prob_threshold=-2.0,
             compression_ratio_threshold=3.0),
        dict(beam_size=1, temperature=[0.0, 0.2, 0.4, 0.6, 0.8]),
    ]
    fixed = borrowed = 0
    for wa, wb in windows:
        a = max(0.0, wa - PAD)
        b = min(len(wave) / SR, wb + PAD)
        clip = wave[int(a * SR):int(b * SR)]
        cap = caption_text_in(caps, wa, wb)
        old = asr_text_in(segs, wa, wb)
        where = f"{int(wa)//60}:{int(wa)%60:02d}~{int(wb)//60}:{int(wb)%60:02d}"

        best: list[dict] = []
        best_len = 0
        for kw in CONFIGS:
            parts, _ = model.transcribe(clip, language=lang, vad_filter=False,
                                        condition_on_previous_text=False, **kw)
            cand = [{"t": round(a + p.start, 2), "end": round(a + p.end, 2),
                     "text": p.text.strip()} for p in parts if p.text.strip()]
            n = sum(len(c["text"]) for c in cand)
            if n > best_len:
                best, best_len = cand, n
            if cap and best_len >= len(cap) * 0.8:
                break        # 자막만큼 건졌으면 나머지 설정은 굳이 돌리지 않는다

        # 여유(PAD)를 두고 잘랐으므로 창 밖에서 시작하는 구간이 딸려 온다. 그대로
        # 넣으면 바깥 구간과 겹쳐 같은 말이 두 번 나온다. 창 안에서 시작한 것만 쓴다.
        best = [c for c in best if wa - 0.5 <= c["t"] < wb]
        best_len = sum(len(c["text"]) for c in best)

        if best_len > len(old) * 1.2:
            for c in best:
                c["repaired"] = True
            print(f"     {where} {len(old)}자 → {best_len}자 (다시 받아씀)")
            fixed += 1
        else:
            print(f"     {where} 다시 받아써도 나아지지 않음")
            continue

        splice(segs, wa, wb, best)

    # 두 번째 판 — 다시 받아써도 여전히 자막보다 얇은 시간대는 자막으로 메운다.
    #
    # 이걸 첫 판에 섞으면 안 된다. whisper 가 조금만 나아져도(1.2배) 그 가지가
    # 먼저 걸려서, 자막이 훨씬 많이 담고 있는데도 안 쓰게 된다. 실제로 재무과의
    # 첫 문장("재무과 말씀드리겠습니다. 1번입니다…")이 그렇게 두 번 사라졌다.
    # 받아쓰기에 두 번의 기회를 다 준 뒤에 판단한다.
    for wa, wb in find_thin_windows(segs, caps):
        cap = caption_text_in(caps, wa, wb)
        old = asr_text_in(segs, wa, wb)
        where = f"{int(wa)//60}:{int(wa)%60:02d}~{int(wb)//60}:{int(wb)%60:02d}"
        if not cap or len(cap) < len(old) * 1.5:
            print(f"     {where} 자막도 더 담고 있지 않음 — 그대로 둠")
            continue
        # 출처가 다르므로 반드시 표시한다. 조용히 섞으면 안 된다.
        splice(segs, wa, wb,
               [{"t": round(wa, 2), "end": round(wb, 2), "text": cap, "fromCaption": True}])
        print(f"     {where} {len(old)}자 → {len(cap)}자 (유튜브 자막에서 가져옴)")
        borrowed += 1

    dedupe(segs)
    return fixed, borrowed


def squash(t: str) -> str:
    return re.sub(r"[\s.,?!]", "", t)


def splice(segs: list[dict], wa: float, wb: float, new: list[dict]) -> None:
    """[wa, wb) 를 새 구간으로 갈아 끼우되, 새 결과에 없는 기존 문장은 남긴다.

    통째로 갈아 끼우면 안 된다. 전체 글자수는 늘었는데 원래 있던 문장 하나가
    조용히 사라질 수 있다 — 실제로 재무과의 첫 문장이 그렇게 없어졌다.
    """
    from difflib import SequenceMatcher

    merged = squash(" ".join(c["text"] for c in new))

    def already_there(text: str) -> bool:
        """새 결과가 이미 담고 있는 말인가.

        글자 그대로 들어 있는지만 보면 안 된다. 자막에서 가져온 문장은 받아쓴
        문장과 표현이 조금씩 다르다("그 내용을 수렴해서…" vs "그 학부모들이…").
        그대로 두면 같은 말이 두 번 나오므로, 겹치는 정도로 판단한다.
        """
        k = squash(text)
        if not k:
            return True
        if k in merged:
            return True
        m = SequenceMatcher(None, k, merged, autojunk=False).find_longest_match(
            0, len(k), 0, len(merged))
        return m.size >= len(k) * 0.6

    survivors = [s for s in segs
                 if wa <= s["t"] < wb
                 and len(squash(s["text"])) >= 8
                 and not already_there(s["text"])]
    for s in survivors:
        s["keptFromFirstPass"] = True
    outside = [s for s in segs if not (wa <= s["t"] < wb)]
    segs[:] = sorted(outside + new + survivors, key=lambda s: s["t"])


def dedupe(segs: list[dict]) -> int:
    """앞뒤로 겹쳐 같은 말이 두 번 들어간 구간을 지운다."""
    out: list[dict] = []
    for s in segs:
        k = squash(s["text"])
        if out and k and (k in squash(out[-1]["text"]) or squash(out[-1]["text"]) in k):
            # 짧은 쪽을 버리고 긴 쪽을 남긴다.
            if len(k) > len(squash(out[-1]["text"])):
                out[-1] = s
            continue
        out.append(s)
    n = len(segs) - len(out)
    segs[:] = out
    return n


# ── 2) 화자 분리 ───────────────────────────────────────────────────────────

def embed_segments(wave, segs: list[dict], min_sec: float = 1.0):
    """구간마다 화자 임베딩(목소리 지문)을 뽑는다."""
    import numpy as np
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    print("   화자 임베딩 모델 준비…")
    enc = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(Path.home() / ".cache" / "spkrec-ecapa"),
        run_opts={"device": "cpu"},
    )

    vecs, idx = [], []
    for i, s in enumerate(segs):
        a, b = int(s["t"] * SR), int(s["end"] * SR)
        clip = wave[a:b]
        # 너무 짧은 구간("예.", "네.")은 목소리 지문이 불안정하다. 군집에서 뺀다.
        if len(clip) < min_sec * SR:
            continue
        with torch.no_grad():
            v = enc.encode_batch(torch.from_numpy(clip[None, :])).squeeze().numpy()
        vecs.append(v / (np.linalg.norm(v) + 1e-9))
        idx.append(i)
        if len(vecs) % 40 == 0:
            print(f"     {len(vecs)}개 구간 처리", flush=True)
    return np.array(vecs), idx


def cluster(vecs, n_speakers: int | None):
    """비슷한 목소리끼리 묶는다. 사람 수를 모르면 실루엣 점수로 고른다."""
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    if len(vecs) < 4:
        return np.zeros(len(vecs), dtype=int)
    if n_speakers:
        return AgglomerativeClustering(n_clusters=n_speakers, metric="cosine",
                                       linkage="average").fit_predict(vecs)
    best, best_score, best_k = None, -1.0, 0
    # 실루엣 점수는 군집 수가 표본 수와 같으면 계산할 수 없다 (k <= n-1).
    for k in range(2, min(16, len(vecs) - 1) + 1):
        lab = AgglomerativeClustering(n_clusters=k, metric="cosine",
                                      linkage="average").fit_predict(vecs)
        if len(set(lab)) < 2:
            continue
        score = silhouette_score(vecs, lab, metric="cosine")
        if score > best_score:
            best, best_score, best_k = lab, score, k
    if best is None:
        return np.zeros(len(vecs), dtype=int)
    print(f"   화자 {best_k}명으로 나눔 (실루엣 {best_score:.3f})")
    return best


# ── 3) 이름 붙이기 ─────────────────────────────────────────────────────────

INTRO = re.compile(r"(?P<name>[가-힣][가-힣\s]{1,12}?(?:과|실|관|센터|연구소|단|팀|청))"
                   r"(?:에서)?\s*(?:[0-9]{1,3}\s*(?:페이지|쪽)\s*)?"
                   r"(?:말씀\s*드리겠습니다|말씀\s*드립니다|보고\s*드리겠습니다)")
CHAIR = re.compile(r"다음\s*부서|다음\s*가겠습니다|가시죠|해\s*주십시오|부탁드립니다|당부드립니다")


def name_clusters(segs: list[dict]) -> dict[int, str]:
    """군집 번호에 이름을 붙인다. 자기소개가 나온 이름을 쓴다."""
    from collections import Counter, defaultdict

    from correct import correct_text
    from segment import canon_dept

    votes: dict[int, Counter] = defaultdict(Counter)
    for s in segs:
        sp = s.get("cluster")
        if sp is None:
            continue
        # 화자 이름도 받아쓴 결과라 오인식이 섞인다. 사전을 먼저 태운다.
        text = correct_text(s["text"])[0]
        m = INTRO.search(text)
        if m:
            votes[sp][canon_dept(re.sub(r"\s+", "", m.group("name")))] += 1
        elif CHAIR.search(text):
            votes[sp]["교육감"] += 1

    names: dict[int, str] = {}
    for sp, c in votes.items():
        # 한 군집에 여러 부서 이름이 나오면 여러 사람이 섞였다는 뜻이다.
        # 압도적인 이름이 있을 때만 붙이고, 아니면 비워 둬 사람이 판단하게 한다.
        (top, n), = c.most_common(1)
        if n >= 2 or len(c) == 1:
            names[sp] = top
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description="오디오 직접 받아쓰기 + 자막 대조 + 화자 분리")
    ap.add_argument("--id", required=True)
    ap.add_argument("--model", default="large-v3-turbo",
                    help="large-v3-turbo(기본, 실시간의 약 2배속) / large-v3(더 정확·훨씬 느림) / small")
    ap.add_argument("--speakers", type=int, help="화자 수를 알면 지정")
    ap.add_argument("--no-diarize", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="이미 받아쓴 결과를 다시 쓰고 복구·화자분리만 다시 한다")
    args = ap.parse_args()

    path = find_audio(args.id)
    if not path:
        print(f"오디오가 없습니다: {AUDIO_DIR}/{args.id}.*")
        print("  → 노트북에서  오디오받기.bat  을 먼저 실행하세요.")
        return 1

    print(f"{args.id} · {path.name} ({path.stat().st_size/1024/1024:.1f} MB)")
    caps = load_captions(args.id)
    print(f"   대조용 유튜브 자막 {len(caps)}줄" if caps else "   유튜브 자막 없음 — 밀도로만 점검합니다")

    cached = ASR_DIR / f"{args.id}.json"
    if args.resume and cached.exists():
        prev = json.loads(cached.read_text(encoding="utf-8"))
        # 복구 **전** 원본에서 다시 시작한다. 이미 복구된 결과에 복구를 또 걸면
        # 비교 기준이 흐려져서 같은 입력에 다른 답이 나온다.
        segs = prev.get("segmentsRaw") or prev["segments"]
        segs = [{k: v for k, v in s.items()
                 if k in ("t", "end", "text")} for s in segs]
        print(f"   이미 받아쓴 {len(segs)}개 구간을 씁니다 (복구 전 원본)")
    else:
        segs = transcribe(path, args.model)
    raw_snapshot = [dict(s) for s in segs]

    fixed, borrowed = repair(path, segs, args.model, caps)

    def save() -> None:
        ASR_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({
            "id": args.id,
            "source": f"whisper:{args.model}",
            "audio": path.name,
            "crosschecked": bool(caps),
            "repairedCount": fixed,
            "fromCaptionCount": borrowed,
            "segments": segs,
            "segmentsRaw": raw_snapshot,
            "segmentCount": len(segs),
            "charCount": sum(len(s["text"]) for s in segs),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 받아쓰기는 26분짜리에 16분 걸리는 가장 비싼 단계다. 뒤따르는 화자 분리가
    # 죽으면(메모리 부족으로 실제로 죽었다) 그 16분이 통째로 날아간다.
    # 그래서 화자 분리 **전에** 한 번 저장한다. --resume 이 여기서 이어받는다.
    save()
    print(f"   중간 저장: {cached.name} (여기서 죽어도 받아쓰기는 남습니다)")

    if not args.no_diarize:
        # whisper 모델과 화자 임베딩 모델을 동시에 들고 있으면 메모리가 모자란다.
        import gc
        gc.collect()
        wave = load_wave(path)
        vecs, idx = embed_segments(wave, segs)
        del wave
        gc.collect()
        if len(vecs) >= 4:
            labels = cluster(vecs, args.speakers)
            for i, lab in zip(idx, labels):
                segs[i]["cluster"] = int(lab)
            names = name_clusters(segs)
            for s in segs:
                if s.get("cluster") in names:
                    s["speaker"] = names[s["cluster"]]
            print(f"   이름 붙은 화자: {sorted(set(names.values()))}")

    save()
    print(f"\n저장: {cached}")
    if borrowed:
        print(f"  ※ {borrowed}개 구간은 받아쓰기가 실패해 유튜브 자막에서 가져왔습니다 "
              f"(화면에 그렇게 표시됩니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
