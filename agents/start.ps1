# 启动脚本 (Windows) - 使用 Conda 环境
# Conda 环境名称: multimodal-agent

$CONDA_ENV_NAME = "multimodal-agent"

Write-Host "🚀 启动多模态智能 Agent 系统..." -ForegroundColor Cyan
Write-Host "🐍 使用 Conda 环境: $CONDA_ENV_NAME" -ForegroundColor Magenta

# 检查 conda 环境是否存在
$envExists = conda env list | Select-String -Pattern "^$CONDA_ENV_NAME\s"
if (-not $envExists) {
    Write-Host "❌ Conda 环境 '$CONDA_ENV_NAME' 不存在!" -ForegroundColor Red
    Write-Host "📝 请先运行: conda create -n $CONDA_ENV_NAME python=3.11 -y" -ForegroundColor Yellow
    Write-Host "📝 然后运行: conda run -n $CONDA_ENV_NAME pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ 未找到 .env 文件，正在从模板创建..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "📝 请编辑 .env 文件，填入您的 DASHSCOPE_API_KEY" -ForegroundColor Yellow
    exit 1
}

# 启动后端服务 (使用 conda run)
Write-Host "🔧 启动后端服务 (FastAPI)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; conda activate $CONDA_ENV_NAME; uvicorn app.main:app --reload --port 8000"

# 等待后端启动
Start-Sleep -Seconds 3

# 启动前端服务 (使用 conda run)
Write-Host "🎨 启动前端服务 (Streamlit)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; conda activate $CONDA_ENV_NAME; streamlit run streamlit_app/app.py --server.port 8501"

Write-Host ""
Write-Host "✅ 服务启动完成!" -ForegroundColor Cyan
Write-Host "📱 前端界面: http://localhost:8501" -ForegroundColor White
Write-Host "📡 API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "💡 提示: 两个 PowerShell 窗口已打开，分别运行前后端服务" -ForegroundColor Gray
Write-Host "💡 如需停止服务，请关闭对应的 PowerShell 窗口" -ForegroundColor Gray
