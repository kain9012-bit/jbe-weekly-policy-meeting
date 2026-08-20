@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem 콘솔 한글 깨짐 방지 (파이썬 출력을 콘솔 코드페이지에 맞춘다)
set PYTHONIOENCODING=cp949:replace

rem 파이썬 실행기 찾기
set "PY="
where python >nul 2>&1 && set "PY=python"
if defined PY goto :found
where py >nul 2>&1 && set "PY=py -3"
if defined PY goto :found
echo.
echo  [오류] 파이썬을 찾지 못했습니다.
echo         python.org 에서 설치하거나, 설치할 때 "Add to PATH" 를 켜세요.
echo.
pause
exit /b 1
:found

echo.
echo  ============================================
echo    주간정책회의 자막 수집
echo  ============================================
echo.
echo  게시판을 확인해서, 아직 자막을 받지 않은 회의만 받습니다.
echo.

%PY% collector\fetch_transcripts.py
set RC=%ERRORLEVEL%

echo.
if not "%RC%"=="0" (
  echo  ------------------------------------------
  echo   [실패] 위에 찍힌 메시지를 확인하세요.
  echo.
  echo   자주 나오는 원인:
  echo    - yt-dlp 미설치 :  pip install yt-dlp youtube-transcript-api
  echo    - 업로드 직후라 자동자막이 아직 만들어지지 않음 (몇 시간 뒤 재시도)
  echo   ------------------------------------------
) else (
  echo  ------------------------------------------
  echo   [완료] data\transcripts 에 저장했습니다.
  echo.
  echo   다음 단계
  echo    1. Claude 에게  "새 회의 정리해줘"  라고 요청
  echo    2. 정리된 파일을 받아 넣고  올리기.bat  실행
  echo   ------------------------------------------
)

echo.
echo  [현재 상태]
%PY% collector\fetch_transcripts.py --check
echo.
pause
exit /b %RC%
