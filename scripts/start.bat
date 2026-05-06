@echo off
echo 启动GMP合规性审计系统...

if not exist config\.env (
    echo 配置文件不存在，正在从示例创建...
    copy config\.env.example config\.env
    echo 请编辑 config\.env 文件，配置API密钥等信息
    pause
    exit /b 1
)

if not exist data\documents mkdir data\documents
if not exist data\processed mkdir data\processed
if not exist data\reports mkdir data\reports
if not exist data\database mkdir data\database

echo 启动后端服务...
cd backend
start "GMP Backend" python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo 启动前端服务...
cd ..\frontend
start "GMP Frontend" npm start

echo.
echo 系统启动完成！
echo 前端访问地址: http://localhost:3000
echo 后端API地址: http://localhost:8000
echo API文档地址: http://localhost:8000/docs

pause
