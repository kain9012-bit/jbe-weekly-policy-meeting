"""1.5단계 · 자막 조각을 '발언' 단위로 묶는다.

    python collector/segment.py --all
    python collector/segment.py --id 2026-W34
    python collector/segment.py --id 2026-W34 --preview   # 저장하지 않고 화면에만

## 왜 필요한가
유튜브 자동자막은 2~3초마다 한 줄씩 끊긴다. 1,200줄짜리 목록은 읽을 수가 없다.
회의록으로 읽으려면 (1) 문장으로 합치고 (2) 누가 말했는지 나눠야 한다.

## '>>' 는 문단 구분이지 화자 구분이 아니다
유튜브 자동자막은 `>>` 를 찍어 주지만, 재어 보면 **20초에 한 번꼴**이다
(W34: 26분에 77개). 같은 사람이 말을 이어 가는 중에도 찍히고, 정작 사람이
바뀌는 자리는 놓치기도 한다. 그래서 여기서는 `>>` 를 **문단 경계로만** 쓴다.

한때 이걸로 '교육감 → 부서 → 교육감' 번갈이를 가정해 화자를 채워 봤는데,
부서 보고 본문이 통째로 교육감 발언으로 뒤집혔다. 그 방식은 버렸다.

## 이 스크립트가 하는 일 / 하지 않는 일
- 한다: 문단 나누기, 문장 병합, **문장으로 합친 뒤** 사전 교정,
        자기소개("○○과 말씀드리겠습니다")로 부서 확정, 부서별 보고 구간(block) 표시
- 하지 않는다: 문맥이 필요한 교정과 발언마다의 화자 배정.
        그건 사람(또는 LLM)이 이 파일을 놓고 채운다.

확실한 것만 `speaker` 에 넣는다. 추측은 넣지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import HUMAN_DIR, REFINED_DIR, TRANSCRIPTS_DIR  # noqa: E402
from correct import correct_text, load_glossary  # noqa: E402

# ── 화자 단서 ──────────────────────────────────────────────────────────────

#: "○○과 말씀드리겠습니다" / "○○실입니다" 같은 자기소개.
#: 자막이 부서명을 띄어 쓰는 경우가 잦아서(민주 시민 교육과) 공백을 허용한다.
SELF_INTRO = re.compile(
    r"(?:^|[.?!]\s*|>>\s*)(?:네[.,]?\s*)?(?:어[,.]?\s*)?"
    r"(?P<name>[가-힣][가-힣\s]{1,12}?(?:과|실|관|센터|연구소|단|팀|청))"
    r"(?:에서)?\s*"
    # "문예체건강과 14페이지 말씀드리겠습니다" 처럼 쪽수·순번이 끼어드는 경우가 있다
    r"(?:[0-9]{1,3}\s*(?:페이지|쪽)\s*)?"
    r"(?:말씀\s*드리겠습니다|말씀\s*드립니다|보고\s*드리겠습니다|입니다)"
)

#: 회의를 진행하거나 지시하는 말투 — 교육감으로 본다.
CHAIR = re.compile(
    r"다음\s*부서|다음\s*가겠습니다|다음으로\s*가|가시죠|해\s*주십시오|해\s*주시기\s*바랍니다|"
    r"부탁드립니다|당부드립니다|검토해\s*주|챙겨\s*주|말씀해\s*주실\s*수\s*있습니까"
)

SENT_END = re.compile(r"[.?!]\s*$")


def strip_marker(text: str) -> str:
    return re.sub(r"^\s*>>\s*", "", text)


def norm(text: str) -> str:
    """자막 조각을 이어 붙일 때 생기는 군더더기를 정리한다."""
    t = re.sub(r"\s+", " ", text).strip()
    # '있습니다.네' 처럼 문장부호 뒤가 붙어 있는 경우 띄운다.
    t = re.sub(r"([.?!])(?=[가-힣A-Za-z0-9])", r"\1 ", t)
    return t.strip()


def split_turns(cues: list[dict]) -> list[list[dict]]:
    """'>>' 가 붙은 줄에서 새 턴을 시작한다."""
    turns: list[list[dict]] = []
    for c in cues:
        if c["text"].lstrip().startswith(">>") or not turns:
            turns.append([])
        turns[-1].append({**c, "text": strip_marker(c["text"])})
    return [t for t in turns if any(x["text"].strip() for x in t)]


def to_sentences(turn: list[dict], max_chars: int = 200) -> list[dict]:
    """턴 안의 자막 조각을 문장 단위로 합친다. 시작 시각은 첫 조각 것을 쓴다."""
    out: list[dict] = []
    buf: list[str] = []
    start = turn[0]["t"]
    for c in turn:
        piece = c["text"].strip()
        if not piece:
            continue
        if not buf:
            start = c["t"]
        buf.append(piece)
        joined = norm(" ".join(buf))
        if SENT_END.search(joined) or len(joined) >= max_chars:
            out.append({"t": start, "text": joined})
            buf = []
    if buf:
        out.append({"t": start, "text": norm(" ".join(buf))})
    return out


def clean_dept(name: str) -> str:
    """'민주 시민 교육과' → '민주시민교육과'. 자막의 들쭉날쭉한 띄어쓰기를 붙인다."""
    return re.sub(r"\s+", "", name)


def canon_dept(name: str) -> str:
    """자막이 들은 부서명을 실제 기구도의 부서명으로 맞춘다.

    '제목과'(재무과), '검사관실'(감사관실), '학교안정과'(학교안전과) 처럼
    ASR 이 비슷하게 들은 이름이 매번 다르게 나온다. 사전 교정으로 대부분 잡히지만
    남는 것은 글자 겹침으로 가장 가까운 부서를 찾는다. 확신이 없으면 원문을 둔다.
    """
    depts: list[str] = load_glossary().get("departments", [])
    if name in depts:
        return name
    # 앞뒤에 군더더기가 붙은 경우 ('그미래교육정책연구소', '제교육협력과')
    for d in sorted(depts, key=len, reverse=True):
        if d in name:
            return d
    # 줄여 부른 경우 ('인권센터' → '전북교육인권센터')
    for d in sorted(depts, key=len):
        if len(name) >= 3 and name in d:
            return d
    best, score = "", 0.0
    for d in depts:
        common = len(set(name) & set(d))
        s = common / max(len(set(name)), len(set(d)))
        if s > score:
            best, score = d, s
    # 글자의 3분의 2 이상이 겹칠 때만 바꾼다. 그 아래는 다른 부서일 수 있다.
    return best if score >= 0.67 else name


def guess_speaker(text: str) -> tuple[str, str]:
    """(확정 화자, 추정 화자) 를 돌려준다. 확정은 자기소개가 있을 때만."""
    m = SELF_INTRO.search(text)
    if m:
        name = clean_dept(m.group("name"))
        if 2 <= len(name) <= 12:
            return name, ""
    if CHAIR.search(text):
        return "", "교육감"
    return "", ""


#: 문장 첫머리의 자기소개 — 여기서 화자가 바뀐 것이 확실하다.
INTRO_AT_HEAD = re.compile(r"^(?:네[.,]?\s*)?(?:어[,.]?\s*)?(?:예[.,]?\s*)?"
                           r"[가-힣][가-힣\s]{1,12}?(?:과|실|관|센터|연구소|단|팀|청)(?:에서)?\s*"
                           r"(?:[0-9]{1,3}\s*(?:페이지|쪽)\s*)?"
                           r"(?:말씀\s*드리겠습니다|말씀\s*드립니다|보고\s*드리겠습니다)")


def resplit(sents: list[dict]) -> list[list[dict]]:
    """'>>' 가 빠진 자리를 자기소개로 메운다.

    유튜브의 '>>' 는 화자 전환을 다 잡아 주지 않는다. 교육감이 "다음 감사실인가요?"
    라고 묻고 곧바로 "감사관실 말씀드리겠습니다" 가 이어지는데 같은 턴에 묶이는
    일이 잦다. 문장 첫머리에 자기소개가 나오면 거기서 다시 자른다.
    """
    groups: list[list[dict]] = [[]]
    for i, s in enumerate(sents):
        if i and INTRO_AT_HEAD.match(s["text"]):
            groups.append([])
        groups[-1].append(s)
    return [g for g in groups if g]


def merge_same_speaker(cues: list[dict]) -> list[dict]:
    """이어지는 발언의 화자가 같으면 한 덩어리로 합치고, 발언 목록을 다시 만든다.

    목소리 군집은 짧은 맞장구("네.", "홍보도 좀 해 주시고.")를 엉뚱한 군집으로
    떼어 놓는 일이 있다. 그러면 교육감이 이어 말하는 20초가 5:06 / 5:08 / 5:10
    세 덩어리로 쪼개져 화면에 나온다. 실제로 그렇게 나왔다.

    화자 이름이 같으면 어차피 한 사람의 말이므로 붙인다. **화자를 모르는 발언은
    붙이지 않는다** — 모르는 사람 둘을 한 사람으로 만들어 버리기 때문이다.
    """
    prev = None
    for c in cues:
        if not c.get("turnStart"):
            continue
        sp = c.get("speaker")
        if sp and sp == prev:
            c.pop("turnStart", None)
            c.pop("speaker", None)
            c.pop("block", None)
            continue
        prev = sp or None
    return [c for c in cues if c.get("turnStart")]


def mark_blocks(heads: list[dict]) -> None:
    """각 발언이 '어느 부서의 보고 구간'에 속하는지 표시한다.

    화자를 발언마다 자동으로 맞히려던 시도는 접었다. 유튜브의 '>>' 는 20초에
    한 번꼴로 찍히는데, 같은 사람이 말을 이어 가는 중에도 찍히고 정작 사람이
    바뀌는 자리는 놓치기도 한다. 이걸로 '교육감 → 부서 → 교육감' 번갈이를
    가정하면 보고 본문이 통째로 교육감 발언으로 뒤집힌다. 실제로 그렇게 나왔다.

    그래서 확실한 것만 남긴다.
      speaker  — 자기소개("○○과 말씀드리겠습니다")나 명확한 진행·지시 말투
      block    — 그 발언이 속한 부서 보고 구간 (다음 부서 자기소개 전까지)
    구간 안에서 누가 말했는지는 사람이 채운다.
    """
    dept = ""
    for h in heads:
        if h.get("speaker") and h["speaker"] != "교육감":
            dept = h["speaker"]
        if h.get("speakerHint") == "교육감":
            h["speaker"] = "교육감"
            h.pop("speakerHint", None)
        if dept:
            h["block"] = dept


def apply_human(meeting_id: str, cues: list[dict]) -> list[dict]:
    """사람이 손으로 고친 내용을 덮어씌우고, 새 발언 목록을 돌려준다.

    `data/human/<회차>.json` 에 이렇게 넣는다.

        {
          "splits":   [176, 281],
          "speakers": { "10": "교육감", "139": "대변인실", "176": "미래교육과" },
          "fixes":    { "149": "… 교육지원청 누리집의 연계 작업을 진행하고 있습니다." }
        }

    키는 문장의 시작 초.
      splits   — 자막이 놓친 화자 전환 자리 (여기서 발언을 새로 시작한다)
      speakers — 그 발언의 화자
      fixes    — 그 문장의 교정된 전문

    자막을 다시 받거나 사전을 고쳐서 segment.py 를 다시 돌려도 이 파일이 있으면
    사람이 한 판단이 그대로 살아난다. 수집은 자동, 정리는 요청인 이 구조에서
    가장 비싼 자원이 사람 손이다. 그 결과를 코드가 덮어쓰게 두면 안 된다.
    """
    path = HUMAN_DIR / f"{meeting_id}.json"
    if not path.exists():
        return []
    human = json.loads(path.read_text(encoding="utf-8"))
    speakers = {int(k): v for k, v in human.get("speakers", {}).items()}
    fixes = {int(k): v for k, v in human.get("fixes", {}).items()}
    splits = {int(x) for x in human.get("splits", [])}

    for c in cues:
        if c["t"] in fixes and fixes[c["t"]] != c["text"]:
            c.setdefault("raw", c["text"])
            c["text"] = fixes[c["t"]]
        # '>>' 가 놓친 화자 전환. 사람이 여기서 갈리는 걸 확인한 자리다.
        if c["t"] in splits:
            c["turnStart"] = True

    heads = [c for c in cues if c.get("turnStart")]
    for h in heads:
        if h["t"] in speakers:
            h["speaker"] = speakers[h["t"]]
            h.pop("speakerHint", None)
    return heads


def from_asr(asr: dict, meta: dict) -> dict:
    """오디오를 직접 받아쓴 결과(`data/asr/`)를 회의록 형태로 바꾼다.

    유튜브 자막에서 출발할 때와 결정적으로 다른 점은 **화자 경계를 추측하지 않아도
    된다**는 것이다. 목소리 군집이 바뀌는 자리가 곧 화자가 바뀌는 자리다.
    `>>` 를 보고 번갈이를 가정하던 것과 비교가 안 된다.
    """
    cues: list[dict] = []
    heads: list[dict] = []
    stats: dict[str, int] = {}
    prev = object()          # 첫 구간은 반드시 새 발언으로 시작하게

    for s in asr["segments"]:
        fixed, hits = correct_text(s["text"])
        item = {"t": int(s["t"]), "text": fixed}
        if fixed != s["text"]:
            item["raw"] = s["text"]
        # 받아쓰기가 실패해 유튜브 자막에서 가져온 구간은 반드시 표시한다.
        # 출처가 다른 글을 조용히 섞으면 읽는 사람이 판단할 근거를 잃는다.
        if s.get("fromCaption"):
            item["fromCaption"] = True
        for k, v in hits.items():
            stats[k] = stats.get(k, 0) + v

        # 너무 짧아서 군집에서 빠진 구간("예.", "네.")은 앞 화자에 붙인다.
        c = s.get("cluster", None)
        if c is None:
            c = prev
        if c != prev:
            item["turnStart"] = True
            if s.get("speaker"):
                item["speaker"] = canon_dept(correct_text(s["speaker"])[0])
            heads.append(item)
        prev = c
        cues.append(item)

    if cues and not cues[0].get("turnStart"):
        cues[0]["turnStart"] = True
        heads.insert(0, cues[0])

    apply_human(meta["id"], cues)
    heads = merge_same_speaker(cues)
    mark_blocks(heads)

    out = {k: meta[k] for k in
           ("id", "postId", "postUrl", "title", "date", "videoId", "videoUrl", "durationSec")
           if k in meta}
    out.update({
        "cues": cues,
        "cueCount": len(cues),
        "charCount": sum(len(c["text"]) for c in cues),
        "turnCount": len(heads),
        "speakerTurns": sum(1 for h in heads if h.get("speaker")),
        "changedLines": sum(1 for c in cues if c.get("raw")),
        "captionFallbacks": sum(1 for c in cues if c.get("fromCaption")),
        "source": asr.get("source", "whisper"),
        "fetchedAt": meta.get("fetchedAt", ""),
        "glossaryHits": [{"rule": k, "count": v}
                         for k, v in sorted(stats.items(), key=lambda kv: -kv[1])],
    })
    return out


def segment(doc: dict) -> dict:
    turns = split_turns(doc["cues"])
    cues: list[dict] = []
    heads: list[dict] = []          # 각 발언의 첫 문장 (화자 정보가 붙는 자리)
    stats: dict[str, int] = {}
    turn_count = 0
    for turn in turns:
        sents = to_sentences(turn)
        if not sents:
            continue
        for group in resplit(sents):
            turn_count += 1
            # 교정은 **문장으로 합친 뒤에** 한다.
            # 2초짜리 자막 조각에 걸면 '노사 / 협력가' 처럼 규칙이 두 줄에 걸쳐
            # 있을 때 아무것도 잡히지 않는다. 그동안 교정이 거의 안 되던 이유다.
            items = []
            for s in group:
                fixed, hits = correct_text(s["text"])
                item = {"t": s["t"], "text": fixed}
                if fixed != s["text"]:
                    item["raw"] = s["text"]
                for k, v in hits.items():
                    stats[k] = stats.get(k, 0) + v
                items.append(item)

            # 화자는 교정된 문장에서 찾는다. '제목과 말씀드리겠습니다' 는
            # 교정 전에는 부서로 잡히지 않는다.
            # 자기소개는 **첫 문장에서만** 인정한다. 발언 중간에 나온 부서명까지
            # 인정하면 "다음 부서로 가시죠"(교육감)가 그 부서 발언으로 뒤집힌다.
            speaker, _ = guess_speaker(items[0]["text"])
            _, hint = guess_speaker(" ".join(it["text"] for it in items))
            items[0]["turnStart"] = True
            if speaker:
                items[0]["speaker"] = canon_dept(speaker)
            elif hint:
                items[0]["speakerHint"] = hint
            heads.append(items[0])
            cues.extend(items)

    # 사람이 고친 게 있으면 그걸 반영한 뒤에 구간을 다시 계산한다.
    apply_human(doc["id"], cues)
    heads = merge_same_speaker(cues)
    mark_blocks(heads)
    turn_count = len(heads)

    out = dict(doc)
    out["cues"] = cues
    out["cueCount"] = len(cues)
    out["charCount"] = sum(len(c["text"]) for c in cues)
    out["turnCount"] = turn_count
    out["speakerTurns"] = sum(1 for c in cues if c.get("speaker"))
    out["changedLines"] = sum(1 for c in cues if c.get("raw"))
    out["glossaryHits"] = [{"rule": k, "count": v}
                           for k, v in sorted(stats.items(), key=lambda kv: -kv[1])]
    out["segmentedAt"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="자막을 발언 단위로 묶기")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--preview", action="store_true", help="저장하지 않고 화면에만 보여준다")
    ap.add_argument("--from-asr", action="store_true",
                    help="유튜브 자막 대신 data/asr/ 의 직접 받아쓴 결과를 쓴다")
    args = ap.parse_args()

    if args.from_asr:
        asr_dir = TRANSCRIPTS_DIR.parent / "asr"
        files = sorted(asr_dir.glob("*.json"))
        if args.id:
            files = [f for f in files if f.stem == args.id]
        if not files:
            print(f"받아쓴 결과가 없습니다: {asr_dir}")
            return 1
        for f in files:
            asr = json.loads(f.read_text(encoding="utf-8"))
            meta_path = TRANSCRIPTS_DIR / f"{f.stem}.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() \
                else {"id": f.stem}
            out = from_asr(asr, meta)
            note = f" · 자막에서 가져온 구간 {out['captionFallbacks']}" if out["captionFallbacks"] else ""
            print(f"  {out['id']}: 받아쓴 구간 {asr['segmentCount']}개 → 발언 {out['turnCount']}개 "
                  f"· 화자 확정 {out['speakerTurns']} · 사전 교정 {out['changedLines']}{note}")
            if not args.preview:
                REFINED_DIR.mkdir(parents=True, exist_ok=True)
                (REFINED_DIR / f"{out['id']}.json").write_text(
                    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    files = sorted(TRANSCRIPTS_DIR.glob("*.json"))
    if args.id:
        files = [f for f in files if f.stem == args.id]
    if not files:
        print("대상이 없습니다.")
        return 1

    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        out = segment(doc)
        print(f"  {out['id']}: 자막 {len(doc['cues'])}줄 → 발언 {out['turnCount']}개 / "
              f"문장 {out['cueCount']}개 · 부서 확인 {out['speakerTurns']}개")
        if args.preview:
            for c in out["cues"][:40]:
                head = f"[{c.get('speaker') or c.get('speakerHint') or '?'}] " if c.get("turnStart") else "    "
                print(f"    {int(c['t'])//60}:{int(c['t'])%60:02d} {head}{c['text']}")
            continue
        REFINED_DIR.mkdir(parents=True, exist_ok=True)
        (REFINED_DIR / f"{out['id']}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
