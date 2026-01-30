@echo off
REM 同时启动后端和 Chainlit 前端

echo ========================================
echo   多模态智能 Agent - 完整启动
echo ========================================
echo.

REM 启动后端 (在新窗口)
echo [1/2] 启动 FastAPI 后端...
start "Agent Backend" cmd /k "cd /d %~dp0 && uvicorn app.main:app --reload --port 8000"

REM 等待后端启动
echo 等待后端启动 (3秒)...
timeout /t 3 /nobreak > nul

REM 启动 Chainlit 前端 (在新窗口)
echo [2/2] 启动 Chainlit 前端...
start "Agent Frontend" cmd /k "cd /d %~dp0chainlit_app && chainlit run cl_app.py -w --port 8501"

echo.
echo ========================================
echo   启动完成!
echo   后端: http://localhost:8000
echo   前端: http://localhost:8501
echo ========================================
echo.

pause
