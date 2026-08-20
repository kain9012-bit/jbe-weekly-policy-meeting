"""주간정책회의 게시판 목록·상세 파싱.

목록 페이지 구조 (2026-08 확인)
    table.bbs_list_t > tbody > tr
        td[0] 번호 또는 "[공지]"
        td[1] 제목 (a[href="/board/view.jbe?...&dataSid=NNNNNNN"])
        td[2] 작성일 "YY.MM.DD"

상세 페이지 구조
    <iframe src="https://www.youtube.com/embed/<videoId>">
"""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import requests

from config import HTTP_TIMEOUT, LIST_URL, SITE, USER_AGENT

DATASID_RE = re.compile(r"dataSid=(\d+)")
EMBED_RE = re.compile(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})")
WATCH_RE = re.compile(r"youtu(?:\.be/|be\.com/watch\?v=)([A-Za-z0-9_-]{11})")
ROW_RE = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
CELL_RE = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S | re.I)
HREF_RE = re.compile(r'<a[^>]+href="([^"]+)"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
# 회의 게시글 제목: "2026년 8월 3주 주간정책회의"
WEEK_RE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})주")


@dataclass
class Post:
    post_id: str          # dataSid
    title: str
    date: str             # YYYY-MM-DD
    url: str
    is_notice: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": SITE,
    })
    return s


def _text(fragment: str) -> str:
    return html.unescape(TAG_RE.sub(" ", fragment)).replace("\xa0", " ").strip()


def _norm_date(raw: str) -> str:
    """'26.08.18' -> '2026-08-18'."""
    m = re.search(r"(\d{2,4})[.\-/](\d{1,2})[.\-/](\d{1,2})", raw)
    if not m:
        return ""
    y, mo, d = m.groups()
    if len(y) == 2:
        y = f"20{y}"
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def fetch_list(session: requests.Session | None = None) -> list[Post]:
    """게시판 1페이지의 게시글 목록을 반환한다 (공지 포함)."""
    session = session or _session()
    res = session.get(LIST_URL, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    return parse_list(res.text)


def parse_list(page_html: str) -> list[Post]:
    posts: list[Post] = []
    seen: set[str] = set()
    for row in ROW_RE.findall(page_html):
        href_m = HREF_RE.search(row)
        if not href_m:
            continue
        href = html.unescape(href_m.group(1))
        sid_m = DATASID_RE.search(href)
        if not sid_m:
            continue
        post_id = sid_m.group(1)
        if post_id in seen:
            continue
        cells = [_text(c) for c in CELL_RE.findall(row)]
        if len(cells) < 2:
            continue
        # 제목은 링크 안쪽 텍스트
        a_block = re.search(
            r"<a[^>]+href=\"" + re.escape(href_m.group(1)) + r"\"[^>]*>(.*?)</a>",
            row, re.S | re.I,
        )
        title = _text(a_block.group(1)) if a_block else (cells[1] if len(cells) > 1 else "")
        date = ""
        for c in reversed(cells):
            date = _norm_date(c)
            if date:
                break
        seen.add(post_id)
        posts.append(Post(
            post_id=post_id,
            title=title,
            date=date,
            url=urljoin(SITE, href),
            is_notice="[공지]" in cells[0] if cells else False,
        ))
    return posts


def fetch_video_id(post: Post, session: requests.Session | None = None) -> str | None:
    """상세 페이지에서 유튜브 videoId를 뽑는다."""
    session = session or _session()
    res = session.get(post.url, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    return parse_video_id(res.text)


def parse_video_id(page_html: str) -> str | None:
    m = EMBED_RE.search(page_html) or WATCH_RE.search(page_html)
    return m.group(1) if m else None


def meeting_id(post: Post) -> str:
    """게시글로부터 안정적인 회의 ID를 만든다. 예) 2026-W34."""
    import datetime as _dt
    if post.date:
        d = _dt.date.fromisoformat(post.date)
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    m = WEEK_RE.search(post.title)
    if m:
        y, mo, wk = m.groups()
        return f"{y}-{int(mo):02d}M{wk}"
    return f"post-{post.post_id}"


def is_meeting_post(post: Post) -> bool:
    """'주간정책회의 생중계 안내' 같은 공지는 제외하고 회의 회차만 고른다."""
    if post.is_notice:
        return False
    return "주간정책회의" in post.title.replace(" ", "") and bool(WEEK_RE.search(post.title))
