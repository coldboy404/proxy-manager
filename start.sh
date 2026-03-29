#!/bin/bash

# Proxy Manager 快速启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Proxy Manager - 快速启动"
echo "============================"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 docker compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose 未安装"
    exit 1
fi

echo "✅ 使用：$COMPOSE_CMD"
echo ""

# 创建数据目录
mkdir -p data logs

# 构建并启动
echo "📦 构建镜像..."
$COMPOSE_CMD build

echo ""
echo "🚀 启动服务..."
$COMPOSE_CMD up -d

echo ""
echo "✅ 启动完成！"
echo ""
echo "📊 Web 面板：http://localhost:5000"
echo "🔌 SOCKS5 入站：localhost:5001"
echo "🌐 HTTP/HTTPS 入站：localhost:5002"
echo ""
echo "📝 查看日志：$COMPOSE_CMD logs -f"
echo "⏹️  停止服务：$COMPOSE_CMD down"
echo ""

# 显示代理使用示例
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "代理使用示例："
echo ""
echo "  🔌 SOCKS5 代理（入站 5001）:"
echo "  curl --socks5 localhost:5001 https://api.ipify.org"
echo "  export ALL_PROXY=socks5://localhost:5001"
echo ""
echo "  🌐 HTTP/HTTPS 代理（入站 5002）:"
echo "  curl -x http://localhost:5002 https://api.ipify.org"
echo "  export HTTP_PROXY=http://localhost:5002"
echo "  export HTTPS_PROXY=http://localhost:5002"
echo ""
echo "  📦 v2rayN 配置:"
echo "    工具 → 全局选项 → HTTP 代理"
echo "    地址：localhost"
echo "    端口：5002"
echo "    协议：HTTP"
echo ""
echo "  ⚙️ 自定义配置："
echo "    访问 Web 面板：http://localhost:5000"
echo "    自由配置入站端口和认证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
