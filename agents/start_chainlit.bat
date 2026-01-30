@echo off
REM Chainlit 前端启动脚本
REM 确保后端已在 http://localhost:8000 运行

echo ========================================
echo   多模态智能 Agent - Chainlit 前端
echo ========================================
echo.

REM 切换到 chainlit_app 目录
cd /d "%~dp0chainlit_app"

REM 启动 Chainlit (端口 8501, 热重载模式)
echo 正在启动 Chainlit 前端...
echo 访问地址: http://localhost:8501
echo.

chainlit run cl_app.py -w --port 8501

pause
