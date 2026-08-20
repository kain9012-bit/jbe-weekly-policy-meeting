"""회의 요약 → 대변인실 '전달사항' hwpx 생성.

    python collector/make_hwpx.py --all
    python collector/make_hwpx.py --id 2026-W34
    python collector/make_hwpx.py --id 2026-W34 --out 전달사항.hwpx

대변인실이 회의 후 배포하는 문서와 같은 모양으로 만든다.
그 문서는 회의 전체 요약이 아니라 **교육감 지시·전달사항만 추린 표**다.

    【 2026. 8. 18.】교육감 주관 주간 정책회의 전달사항
    【정책회의 2026. 8. 18.(화) 09:00】
    ┌─────────────────────┬──────────┬────┐
    │ 내용                 │ 추진부서  │비고│
    │ ❍ 제목               │ 부서명    │    │
    │  - 세부 내용          │ (보조부서)│    │
    └─────────────────────┴──────────┴────┘

## 왜 템플릿을 쓰나
hwpx 는 글꼴·문단모양·테두리 정의가 header.xml 에 모여 있고 본문은 그 ID를 참조한다.
빈 문서에서 만들면 그 정의를 전부 새로 써야 해서 실제 배포 문서와 모양이 달라진다.
그래서 대변인실이 준 실제 파일을 templates/ 에 두고, **표의 행만 갈아 끼운다.**
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, MEETINGS_DIR, ROOT  # noqa: E402

TEMPLATE = ROOT / "templates" / "전달사항_양식.hwpx"
OUT_DIR = DATA_DIR / "handouts"
SECTION = "Contents/section0.xml"

TR = re.compile(r"<hp:tr>.*?</hp:tr>", re.S)
TC = re.compile(r"<hp:tc\b.*?</hp:tc>", re.S)
P = re.compile(r"<hp:p\b[^>]*>.*?</hp:p>", re.S)
CHARPR = re.compile(r'charPrIDRef="(\d+)"')
PARAPR = re.compile(r'paraPrIDRef="(\d+)"')
ROWADDR = re.compile(r'rowAddr="\d+"')
WEEKDAY = "월화수목금토일"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def para(template_p: str, text: str) -> str:
    """문단 하나를 만든다. 서식(문단모양·글자모양)은 템플릿 것을 그대로 쓴다."""
    ppr = PARAPR.search(template_p)
    cpr = CHARPR.search(template_p)
    ppr = ppr.group(1) if ppr else "0"
    cpr = cpr.group(1) if cpr else "0"
    body = f"<hp:run charPrIDRef=\"{cpr}\"><hp:t>{esc(text)}</hp:t></hp:run>" if text \
        else f"<hp:run charPrIDRef=\"{cpr}\"></hp:run>"
    return (f'<hp:p id="0" paraPrIDRef="{ppr}" styleIDRef="0" '
            f'pageBreak="0" columnBreak="0" merged="0">{body}</hp:p>')


def fill_cell(cell_tpl: str, lines: list[str]) -> str:
    """셀 하나의 문단을 통째로 갈아 끼운다. 첫 줄은 제목 서식, 나머지는 본문 서식."""
    paras = P.findall(cell_tpl)
    if not paras:
        return cell_tpl
    head_tpl = paras[0]
    body_tpl = paras[1] if len(paras) > 1 else paras[0]
    made = [para(head_tpl, lines[0] if lines else "")]
    made += [para(body_tpl, ln) for ln in lines[1:]]
    # 셀에서 문단 영역만 교체한다 (cellAddr·cellSz 등 나머지 속성은 보존)
    first, last = cell_tpl.find(paras[0]), cell_tpl.rfind(paras[-1]) + len(paras[-1])
    return cell_tpl[:first] + "".join(made) + cell_tpl[last:]


def build_row(row_tpl: str, row_no: int, content: list[str],
              depts: list[str], note: str) -> str:
    cells = TC.findall(row_tpl)
    if len(cells) < 3:
        return row_tpl
    filled = [
        fill_cell(cells[0], content),
        fill_cell(cells[1], depts or [""]),
        fill_cell(cells[2], [note]),
    ]
    out = row_tpl
    for old, new in zip(cells, filled):
        out = out.replace(old, new, 1)
    return ROWADDR.sub(f'rowAddr="{row_no}"', out)


def kor_date(iso: str) -> tuple[str, str]:
    import datetime as dt
    d = dt.date.fromisoformat(iso)
    return (f"{d.year}. {d.month}. {d.day}.",
            f"{d.year}. {d.month}. {d.day}.({WEEKDAY[d.weekday()]})")


def handout_rows(meeting: dict) -> list[tuple[list[str], list[str], str]]:
    """지시사항을 (내용 줄들, 추진부서 줄들, 비고) 로 바꾼다."""
    rows = []
    for d in meeting.get("directives", []):
        title = (d.get("title") or "").strip() or d["text"].strip()
        lines = [f"❍ {title}"]
        # 제목과 본문이 같으면 본문 줄을 또 넣지 않는다.
        if d["text"].strip() != title:
            lines.append(f" - {d['text'].strip()}")
        if d.get("due"):
            lines.append(f" - 기한: {d['due']}")
        depts = [x.strip() for x in (d.get("dept") or "").split("/") if x.strip()] or ["모든 기관"]
        rows.append((lines, depts, d.get("note", "")))
    return rows


def make(meeting: dict, out_path: Path) -> Path:
    if not TEMPLATE.exists():
        raise SystemExit(f"양식 파일이 없습니다: {TEMPLATE}")

    with zipfile.ZipFile(TEMPLATE) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}
    xml = blobs[SECTION].decode("utf-8")

    rows = TR.findall(xml)
    if len(rows) < 3:
        raise SystemExit("양식에서 표를 찾지 못했습니다.")
    header_row, body_tpl, footer_row = rows[0], rows[1], rows[-1]

    data = handout_rows(meeting)
    new_rows = [header_row]
    for i, (content, depts, note) in enumerate(data, start=1):
        new_rows.append(build_row(body_tpl, i, content, depts, note))
    new_rows.append(ROWADDR.sub(f'rowAddr="{len(data) + 1}"', footer_row))

    # 표 안의 행 전체를 교체
    start = xml.find(rows[0])
    end = xml.rfind(rows[-1]) + len(rows[-1])
    xml = xml[:start] + "".join(new_rows) + xml[end:]
    xml = re.sub(r'rowCnt="\d+"', f'rowCnt="{len(new_rows)}"', xml, count=1)

    # 제목·부제의 날짜를 회의 날짜로.
    # 제목의 날짜는 【 · 날짜 · 】 가 각각 다른 hp:run 으로 쪼개져 있어서
    # 【…】 통째로는 안 잡힌다. hp:t 안의 날짜 문자열을 직접 바꾼다.
    short, long = kor_date(meeting["date"])
    xml = re.sub(r"<hp:t>\d{4}\. \d{1,2}\. \d{1,2}\.</hp:t>", f"<hp:t>{short}</hp:t>", xml)
    xml = re.sub(r"【정책회의[^】]*】", f"【정책회의 {long} 09:00】", xml)

    blobs[SECTION] = xml.encode("utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # mimetype 은 규격상 맨 앞에 무압축으로 들어가야 한다.
        z.writestr(zipfile.ZipInfo("mimetype"), blobs["mimetype"], zipfile.ZIP_STORED)
        for n in names:
            if n != "mimetype":
                z.writestr(n, blobs[n])
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="전달사항 hwpx 생성")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", help="회차 (예: 2026-W34)")
    ap.add_argument("--out", help="출력 경로 (지정하지 않으면 data/handouts/<회차>.hwpx)")
    args = ap.parse_args()

    files = sorted(MEETINGS_DIR.glob("*.json"))
    if args.id:
        files = [f for f in files if f.stem == args.id]
    elif not args.all:
        files = [f for f in files if not (OUT_DIR / f"{f.stem}.hwpx").exists()]

    if not files:
        print("만들 대상이 없습니다.")
        return 0

    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        out = Path(args.out) if args.out else OUT_DIR / f"{m['id']}.hwpx"
        make(m, out)
        print(f"  {m['id']} · 지시사항 {len(m.get('directives', []))}건 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
