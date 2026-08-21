"""발행 전 검증 — 실제 내용은 Skill 쪽에 있다.

    python scripts/verify.py

같은 검사를 두 벌 두면 반드시 어긋난다. 원본은 한 곳에만 둔다.
  원본:  skill/jbe-weekly-meeting/scripts/verify.py
이 파일은 저장소 루트에서 짧게 부르기 위한 껍데기다.
"""
import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "skill" / "jbe-weekly-meeting" / "scripts" / "verify.py"
if not TARGET.exists():
    sys.exit(f"검증 스크립트가 없습니다: {TARGET}")
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
