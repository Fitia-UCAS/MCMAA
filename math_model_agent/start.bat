@echo off
REM === 激活 conda 环境 ===
call D:\Anaconda\Scripts\activate.bat mcmaa_tk

REM === 切换到后端目录 ===
cd /d E:\repo1\MCM\mcmaa\math_model_agent

REM === 启动后端服务 ===
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
