#!/bin/bash

# Proxy Manager 停止脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "⏹️  停止 Proxy Manager..."

# 检查 docker compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose 未找到"
    exit 1
fi

# 停止服务
$COMPOSE_CMD down

echo ""
echo "✅ 服务已停止"
echo ""
echo "📁 数据目录：./data (已保留)"
echo "📝 日志目录：./logs (已保留)"
echo ""
echo "重新启动：./start.sh"
echo ""
