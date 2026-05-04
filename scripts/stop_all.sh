#!/bin/bash

echo "======================================"
echo "  AegisLink - 停止所有服务"
echo "======================================"

if [ -f ".service_pids" ]; then
    PIDS=$(cat .service_pids)
    echo "停止进程: $PIDS"
    kill $PIDS 2>/dev/null
    rm .service_pids
    echo "✓ 所有服务已停止"
else
    echo "尝试停止所有相关进程..."
    pkill -f "src.iam.service" 2>/dev/null
    pkill -f "src.agents" 2>/dev/null
    pkill -f "src.web_console" 2>/dev/null
    lsof -ti:8080 | xargs kill 2>/dev/null
    echo "✓ 服务停止完成"
fi

echo "======================================"
