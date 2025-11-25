#!/bin/bash

# 启动后端
echo "Starting backend..."
cd backend
python main.py &
BACKEND_PID=$!

# 启动前端
echo "Starting frontend..."
cd ../frontend
pnpm dev &
FRONTEND_PID=$!

# 等待进程结束
wait $BACKEND_PID $FRONTEND_PID
