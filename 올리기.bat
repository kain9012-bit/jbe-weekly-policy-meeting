@echo off
setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo    깃허브에 올리기
echo  ============================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo  [오류] git 이 설치돼 있지 않습니다.  https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

if not exist ".git" (
  echo  [오류] 아직 git 저장소가 아닙니다.
  echo.
  pause
  exit /b 1
)

rem 발행 전 검증. 여기서 걸리면 올리지 않는다.
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (where py >nul 2>&1 && set "PY=py -3")
if defined PY (
  echo  [검증] 인용문, 부서명, 연결 순서를 확인합니다...
  echo.
  %PY% scripts\verify.py
  if errorlevel 1 (
    echo.
    echo  ------------------------------------------
    echo   [중단] 검증에 걸렸습니다. 고치기 전에는 올리지 않습니다.
    echo  ------------------------------------------
    echo.
    pause
    exit /b 1
  )
  echo.
)

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo  올릴 변경 사항이 없습니다.
  echo.
  pause
  exit /b 0
)

echo  [바뀐 파일]
git diff --cached --name-status
echo.

set MSG=%date% 회의 자료 갱신
git commit -m "%MSG%"
if errorlevel 1 (
  echo  [실패] 커밋에 실패했습니다.
  echo.
  pause
  exit /b 1
)

git push
if errorlevel 1 (
  echo.
  echo  [실패] 푸시에 실패했습니다. 인증 정보나 네트워크를 확인하세요.
  echo.
  pause
  exit /b 1
)

echo.
echo  ------------------------------------------
echo   [완료] 올렸습니다. 1~2분 뒤 반영됩니다.
echo.
echo   https://jbe-weekly-policy-meeting.vercel.app/
echo   https://kain9012-bit.github.io/jbe-weekly-policy-meeting/
echo  ------------------------------------------
echo.
pause
