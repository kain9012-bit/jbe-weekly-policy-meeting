"""Skill 폴더를 .skill 파일로 묶는다.

    python skill/build.py        # skill/jbe-weekly-meeting.skill

Skill 을 고쳤으면 이걸로 다시 묶어서 Claude 에 저장한다.
저장소에 폴더를 두는 이유는, 고친 내역이 커밋에 남아야 하기 때문이다.
"""
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "jbe-weekly-meeting"
OUT = HERE / "jbe-weekly-meeting.skill"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            z.write(p, p.relative_to(HERE).as_posix())
print(f"{OUT}  ({OUT.stat().st_size:,} bytes)")
