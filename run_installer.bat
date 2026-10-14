@echo off
chcp 65001 >nul
cd /d "%~dp0"
py installer
wn_ko_installer.py
if errorlevel 1 pause
