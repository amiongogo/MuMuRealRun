@echo off
setlocal
cd /d "%~dp0"

title MuMuRealRun - 路线可视化生成器

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    pause
    exit /b 1
)

python route_editor.py
if errorlevel 1 (
    echo [ERROR] Failed to start route editor!
    pause
)
