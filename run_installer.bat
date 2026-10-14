@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 실제로 동작하는 Python 3 (tkinter 포함)이 있는지 확인한다.
rem 'where py' 만으로는 Microsoft Store 바로가기(빈 껍데기)를 걸러내지 못한다.
py -3 -c "import tkinter" >nul 2>nul
if %errorlevel%==0 (
  py -3 installer\nwn_ko_installer.py
  if errorlevel 1 pause
) else (
  echo Python 3 이 설치되어 있지 않거나 tkinter 를 사용할 수 없습니다.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo winget 이 없어 자동 설치를 할 수 없습니다. 열리는 페이지에서 Python 3 을 설치하세요.
    echo 설치할 때 "tcl/tk and IDLE" 와 "py launcher" 를 체크하고, 끝나면 이 파일을 다시 실행하세요.
    start https://www.python.org/downloads/
  ) else (
    choice /c YN /m "winget 으로 Python 3 을 지금 설치할까요"
    if errorlevel 2 (
      start https://www.python.org/downloads/
    ) else (
      winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
      echo.
      echo 설치가 끝났습니다. 이 창을 닫고 run_installer.bat 을 다시 실행하세요.
    )
  )
  pause
)
