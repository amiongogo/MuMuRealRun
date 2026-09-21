@echo off
setlocal
cd /d "%~dp0"

title MuMuRealRun

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.8+ and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

python -c "import rich, yaml" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing required dependencies: rich, pyyaml...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies! Please check your network connection.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed successfully.
    echo.
)

python main.py %*
if errorlevel 1 (
    echo.
    echo [INFO] Program terminated with an error.
    pause
)
