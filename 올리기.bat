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
  echo  [오류] 아직 git 저장소가 아닙니다. 아래를 한 번만 실행하세요.
  echo.
  echo    git init
  echo    git add .
  echo    git commit -m "first"
  echo    git branch -M main
  echo    git remote add origin https://github.com/kain9012-bit/jbe-weekly-policy-meeting.git
  echo    git push -u origin main
  echo.
  pause
  exit /b 1
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
echo   [완료] 올렸습니다.
echo   1~2분 뒤 웹페이지에 반영됩니다.
echo   https://kain9012-bit.github.io/jbe-weekly-policy-meeting/
echo  ------------------------------------------
echo.
pause
