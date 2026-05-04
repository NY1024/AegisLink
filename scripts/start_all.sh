#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

echo "======================================"
echo "  AegisLink - 启动所有服务"
echo "======================================"

if [ -d "venv" ]; then
    echo ""
    echo "[1/4] 激活虚拟环境..."
    source venv/bin/activate
    echo "✓ 虚拟环境已激活"
fi

echo ""
echo "[2/4] 创建必要目录..."
mkdir -p logs audit_logs
echo "✓ 目录创建完成"

echo ""
echo "[3/4] 启动IAM授权服务 (端口 8000)..."
python -m src.iam.service > logs/iam.log 2>&1 &
IAM_PID=$!
echo "IAM服务 PID: $IAM_PID"

sleep 2

echo ""
echo "[4/4] 启动Agent服务..."

python -m src.agents.data_agent > logs/data_agent.log 2>&1 &
DATA_PID=$!
echo "企业数据Agent PID: $DATA_PID"

python -m src.agents.search_agent > logs/search_agent.log 2>&1 &
SEARCH_PID=$!
echo "外部检索Agent PID: $SEARCH_PID"

sleep 2

python -m src.agents.doc_assistant > logs/doc_assistant.log 2>&1 &
DOC_PID=$!
echo "文档助手Agent PID: $DOC_PID"

sleep 2

python -m src.web_console > logs/web_console.log 2>&1 &
WEB_PID=$!
echo "Web控制台 PID: $WEB_PID"

echo ""
echo "======================================"
echo "  所有服务启动完成!"
echo "======================================"
echo ""
echo "服务状态:"
echo "  - IAM授权服务: http://localhost:8000"
echo "  - 文档助手Agent: http://localhost:8001"
echo "  - 企业数据Agent: http://localhost:8002"
echo "  - 外部检索Agent: http://localhost:8003"
echo "  - Web控制台: http://localhost:8080"
echo ""
echo "日志文件: logs/"
echo "审计日志: audit_logs/audit_logs.jsonl"
echo ""
echo "运行演示: python -m src.demo"
echo "停止服务: pkill -f 'src.iam.service' && pkill -f 'src.agents'"
echo ""
echo "进程ID:"
echo "  IAM: $IAM_PID"
echo "  Data: $DATA_PID"
echo "  Search: $SEARCH_PID"
echo "  Doc: $DOC_PID"
echo "  Web: $WEB_PID"
echo "======================================"

echo "$IAM_PID $DATA_PID $SEARCH_PID $DOC_PID $WEB_PID" > .service_pids
