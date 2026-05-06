#!/bin/bash
echo "启动GMP合规性审计系统..."

if [ ! -f config/.env ]; then
    echo "配置文件不存在，正在从示例创建..."
    cp config/.env.example config/.env
    echo "请编辑 config/.env 文件，配置API密钥等信息"
    exit 1
fi

mkdir -p data/{documents,processed,reports,database}

echo "启动后端服务..."
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "启动前端服务..."
cd ../frontend
npm start &
FRONTEND_PID=$!

echo "系统启动完成！"
echo "前端访问地址: http://localhost:3000"
echo "后端API地址: http://localhost:8000"
echo "API文档地址: http://localhost:8000/docs"

wait $BACKEND_PID $FRONTEND_PID
