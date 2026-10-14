@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py installer\nwn_ko_installer.py
  if errorlevel 1 pause
) else (
  echo Python 3 이 설치되어 있지 않습니다.
  choice /c YN /m "winget 으로 Python 3 을 지금 설치할까요"
  if errorlevel 2 (
    start https://www.python.org/downloads/
  ) else (
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo 설치가 끝나면 이 파일을 다시 실행하세요.
  )
  pause
)
