# MuMuRealRun PowerShell 快速启动脚本
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          MuMuRealRun - 运动模拟与虚拟定位控制台" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未检测到 Python 环境！请先安装 Python 3.8+ 并添加至 PATH。" -ForegroundColor Red
    Pause
    Exit 1
}

# 检查依赖
$checkDeps = python -c "import rich, yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] 正在安装依赖库 (rich, pyyaml)..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 依赖安装失败，请检查网络！" -ForegroundColor Red
        Pause
        Exit 1
    }
    Write-Host "[✔] 依赖安装完成！" -ForegroundColor Green
}

# 启动主程序
python main.py @args
