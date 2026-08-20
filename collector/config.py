"""공통 설정값."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"    # 1단계: 자막 원문 + 사전 교정
REFINED_DIR = DATA_DIR / "refined"            # 1.5단계: LLM 문맥 교정 + 화자
MEETINGS_DIR = DATA_DIR / "meetings"          # 2단계: LLM 요약
INDEX_PATH = DATA_DIR / "index.json"
GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary.json"

# 주간정책회의 게시판
BOARD_ID = "BBS_0000681"
MENU_CD = "DOM_000000507001000000"
CONTENTS_SID = "3249"
SITE = "https://www.jbe.go.kr"
LIST_URL = (
    f"{SITE}/jbeducation/board/list.jbe"
    f"?boardId={BOARD_ID}&menuCd={MENU_CD}&contentsSid={CONTENTS_SID}&cpath=%2Fjbeducation"
)

# 게시판이 해외 IP를 막는 경우가 있어 일반 브라우저 UA로 접근한다.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 30

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()  # gemini | openai
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
# 교정 단계는 자막 전문을 그대로 다시 출력하므로 토막을 나눈다.
# 10분(약 200큐·3,600자)이면 출력이 4k 토큰 안팎이라 잘릴 위험이 없다.
REFINE_WINDOW_SEC = int(os.getenv("REFINE_WINDOW_SEC", "600"))
REFINE_OVERLAP = int(os.getenv("REFINE_OVERLAP", "2"))  # 앞 토막 끝 몇 줄을 문맥으로 붙일지
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 자막
CAPTION_LANG = os.getenv("CAPTION_LANG", "ko")
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES_FILE")  # 선택. 클라우드 러너에서만 필요.
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "900"))  # 60분 영상도 여유 있게

# 요약을 건너뛰고 자막 수집·교정까지만 수행 (LLM 키가 없을 때)
SKIP_SUMMARY = os.getenv("SKIP_SUMMARY", "").lower() in ("1", "true", "yes")
