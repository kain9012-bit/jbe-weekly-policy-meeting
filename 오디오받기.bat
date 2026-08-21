@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=cp949:replace

set "PY="
where python >nul 2>&1 && set "PY=python"
if defined PY goto :found
where py >nul 2>&1 && set "PY=py -3"
if defined PY goto :found
echo.
echo  [오류] 파이썬을 찾지 못했습니다.
echo.
pause
exit /b 1
:found

echo.
echo  ============================================
echo    회의 오디오 내려받기
echo  ============================================
echo.
echo  영상의 소리만 받습니다. 화면은 받지 않습니다.
echo  1시간 회의가 30MB 안쪽입니다.
echo.

%PY% -m pip install -q -U yt-dlp
%PY% collector\fetch_audio.py %*
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo  ------------------------------------------
  echo   받은 파일은  data\audio\  에 있습니다.
  echo   Claude 에게 "오디오 올렸어" 라고 알려 주세요.
  echo  ------------------------------------------
) else (
  echo  ------------------------------------------
  echo   [실패] 위 메시지를 확인하세요.
  echo  ------------------------------------------
)
echo.
pause
exit /b %RC%
