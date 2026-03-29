#!/bin/bash

# Proxy Manager 测试脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧪 Proxy Manager 测试"
echo "===================="
echo ""

# 检查服务是否运行
if ! curl -s http://localhost:5000/api/stats > /dev/null 2>&1; then
    echo "❌ Web 服务未运行，请先启动服务：./start.sh"
    exit 1
fi

echo "✅ Web 服务正常运行"
echo ""

# 测试 API
echo "📊 测试 API 接口..."
echo ""

echo "1️⃣  统计信息:"
curl -s http://localhost:5000/api/stats | jq '.'
echo ""

echo "2️⃣  SOCKS5 信息:"
curl -s http://localhost:5000/api/socks5 | jq '.'
echo ""

echo "3️⃣  HTTP 代理信息:"
curl -s http://localhost:5000/api/http-proxy | jq '.'
echo ""

# 测试代理连接
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔌 测试代理连接..."
echo ""

echo "4️⃣  测试 HTTP 代理 (端口 5002):"
if curl -s -x http://localhost:5002 --connect-timeout 5 https://api.ipify.org?format=json 2>/dev/null; then
    echo " ✅ HTTP 代理测试成功"
else
    echo " ⚠️  HTTP 代理暂无可用上游代理（先获取并测试代理）"
fi
echo ""

echo "5️⃣  测试 SOCKS5 代理 (端口 5001):"
if curl -s --socks5 localhost:5001 --connect-timeout 5 https://api.ipify.org?format=json 2>/dev/null; then
    echo " ✅ SOCKS5 代理测试成功"
else
    echo " ⚠️  SOCKS5 代理暂无可用上游代理（先获取并测试代理）"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ 测试完成！"
echo ""
echo "📝 提示:"
echo "  - 如果代理测试失败，请先在 Web 面板点击「获取代理」和「开始测速」"
echo "  - 访问 Web 面板：http://localhost:5000"
echo "  - 自定义配置：在 Web 面板「入站代理配置」区域修改端口"
echo ""
