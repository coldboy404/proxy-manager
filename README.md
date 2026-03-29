# Proxy Manager - 智能代理管理系统

🚀 自动从 Proxifly 获取免费代理，智能测速，按延迟排序，提供 Web 管理面板。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📥 **自动获取** | 从 Proxifly 实时拉取最新代理（每 5 分钟更新） |
| 🌐 **多协议支持** | HTTP、HTTPS、SOCKS4、SOCKS5 |
| 🌍 **地区筛选** | 按国家/地区筛选代理 |
| 🚀 **智能测速** | 随机选取 10-15 个代理进行延迟测试 |
| 📊 **延迟排序** | 自动按延迟从低到高排序 |
| 🔄 **自动刷新** | 后台定时重新测速，保持代理池新鲜 |
| 🎨 **Web 面板** | 美观的管理界面，实时查看状态 |
| 🔌 **SOCKS5 入站** | 支持 SOCKS5 代理服务器，可直接连接使用代理池 |
| 🌐 **HTTP/HTTPS 入站** | v2rayN 风格本地代理，映射到 5002 端口 |

## 🚀 快速启动

### 方式一：一键启动脚本（推荐）

```bash
cd /root/.openclaw/workspace/proxy-manager

# 启动服务
./start.sh

# 停止服务
./stop.sh
```

### 方式二：Docker Compose

```bash
cd /root/.openclaw/workspace/proxy-manager

# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 访问：
# Web 面板：http://localhost:5000
# SOCKS5 代理：localhost:5001
# HTTP/HTTPS 代理：localhost:5002 (v2rayN 风格)
```

### 方式三：Docker 直接运行

```bash
# 构建镜像
docker build -t proxy-manager .

# 运行容器
docker run -d \
  --name proxy-manager \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e TEST_INTERVAL=60 \
  -e TEST_COUNT=15 \
  proxy-manager
```

### 方式三：本地运行（需要 Python 3.11+）

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app/proxy_manager.py

# 访问 http://localhost:5000
```

## 🎛️ Web 面板功能

访问 `http://localhost:5000` 打开管理面板：

### 实时统计
- 总代理数
- 可用代理数
- 平均延迟
- 已测试数量

### 配置选项
- **代理类型**: 全部/HTTP/HTTPS/SOCKS4/SOCKS5
- **国家/地区**: 按地区筛选
- **测试数量**: 每次测速的代理数量（默认 15）
- **自动测速间隔**: 后台重新测速的间隔（默认 60 秒）

### 操作按钮
- 📥 **获取代理**: 从 Proxifly 拉取最新列表
- 🚀 **开始测速**: 手动触发测速
- 🔄 **刷新列表**: 刷新显示
- 💾 **保存配置**: 保存当前配置

## ⚙️ 环境变量配置

### 基础配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POLL_INTERVAL` | `300` | 代理列表更新间隔（秒） |
| `TEST_INTERVAL` | `60` | 自动测速间隔（秒） |
| `TEST_COUNT` | `15` | 每次测试的代理数量 |
| `TIMEOUT` | `5` | 测速超时（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DATA_DIR` | `/app/data` | 数据目录（容器内） |

### SOCKS5 服务器配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOCKS5_ENABLED` | `true` | 是否启用 SOCKS5 服务器 |
| `SOCKS5_HOST` | `0.0.0.0` | SOCKS5 监听地址 |
| `SOCKS5_PORT` | `5001` | SOCKS5 监听端口 |
| `SOCKS5_AUTH` | `false` | 是否启用认证 |
| `SOCKS5_USER` | `proxyuser` | SOCKS5 用户名 |
| `SOCKS5_PASS` | `proxypass` | SOCKS5 密码 |
| `SOCKS5_ROTATE` | `request` | 代理轮换策略：`request`/`connection` |

### HTTP/HTTPS 代理服务器配置（v2rayN 风格）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HTTP_PROXY_ENABLED` | `true` | 是否启用 HTTP 代理服务器 |
| `HTTP_PROXY_HOST` | `0.0.0.0` | HTTP 代理监听地址 |
| `HTTP_PROXY_PORT` | `5002` | HTTP 代理监听端口 |
| `HTTP_PROXY_AUTH` | `false` | 是否启用认证 |
| `HTTP_PROXY_USER` | `proxyuser` | HTTP 代理用户名 |
| `HTTP_PROXY_PASS` | `proxypass` | HTTP 代理密码 |

### 自定义配置示例

> 默认端口：**SOCKS5 = 5001**，**HTTP/HTTPS = 5002**。
> 下面示例如果改成别的端口，表示“自定义端口”，不是默认值。

**调整测速参数：**
```yaml
# docker-compose.yml
environment:
  - TEST_INTERVAL=30      # 每 30 秒测速一次
  - TEST_COUNT=20         # 每次测试 20 个代理
  - TIMEOUT=10            # 10 秒超时
  - LOG_LEVEL=DEBUG       # 详细日志
```

**启用 SOCKS5 认证（保持默认端口 5001）：**
```yaml
environment:
  - SOCKS5_ENABLED=true
  - SOCKS5_PORT=5001
  - SOCKS5_AUTH=true
  - SOCKS5_USER=myuser
  - SOCKS5_PASS=mypassword
```

**自定义 SOCKS5 端口（示例改成 1080）：**
```yaml
ports:
  - "1080:1080"  # 主机 1080 -> 容器 1080
environment:
  - SOCKS5_PORT=1080
```

**自定义 HTTP 代理端口（示例改成 5003）：**
```yaml
ports:
  - "5003:5003"  # 主机 5003 -> 容器 5003
environment:
  - HTTP_PROXY_PORT=5003
```

**只启用 HTTP 代理（禁用 SOCKS5，保持默认 HTTP 端口 5002）：**
```yaml
environment:
  - SOCKS5_ENABLED=false
  - HTTP_PROXY_ENABLED=true
  - HTTP_PROXY_PORT=5002
```

## 📊 API 接口

### 获取 HTTP 代理连接信息
```bash
curl http://localhost:5000/api/http-proxy
```

响应示例：
```json
{
  "success": true,
  "http_proxy": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 5002,
    "auth_enabled": false,
    "username": null,
    "password": null,
    "connections": 10,
    "requests_handled": 150
  }
}
```

### 获取 SOCKS5 连接信息
```bash
curl http://localhost:5000/api/socks5
```

响应示例：
```json
{
  "success": true,
  "socks5": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 5001,
    "auth_enabled": false,
    "username": null,
    "password": null,
    "connections": 5,
    "bytes_transferred": 1024000
  }
}
```

### 获取统计信息
```bash
curl http://localhost:5000/api/stats
```

### 获取代理列表
```bash
# 获取所有代理
curl http://localhost:5000/api/proxies

# 只获取可用代理（按延迟排序）
curl http://localhost:5000/api/proxies?working=true
```

### 获取代理
```bash
curl -X POST http://localhost:5000/api/proxies/fetch \
  -H "Content-Type: application/json" \
  -d '{"type": "all", "country": "US"}'
```

### 测试代理
```bash
curl -X POST http://localhost:5000/api/proxies/test \
  -H "Content-Type: application/json" \
  -d '{"count": 15, "country": "US", "protocol": "https"}'
```

### 保存配置
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{"country": "US", "protocol": "https", "test_interval": 60}'
```

## 📁 数据目录结构

```
data/
├── config.json          # 当前配置
└── (未来可扩展：代理历史数据)
```

## 🔌 在你的项目中使用

### 方式一：HTTP/HTTPS 代理（v2rayN 风格，推荐）

启动后，Docker 会暴露 `5002` 端口作为 HTTP/HTTPS 代理入口，类似 v2rayN 的本地代理：

```bash
# cURL 使用 HTTP 代理
curl -x http://localhost:5002 https://api.ipify.org?format=json

# 设置环境变量（全局生效）
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002

# Python 使用
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002
import requests
response = requests.get('https://api.ipify.org')
```

**v2rayN 配置：**
1. 打开 v2rayN → 工具 → 全局选项
2. HTTP 代理：`localhost`
3. 端口：`5002`
4. 协议：`HTTP`
5. 保存

**Windows 系统代理：**
- 设置 → 网络和 Internet → 代理 → 手动设置代理
- 地址：`localhost`，端口：`5002`

**浏览器扩展（SwitchyOmega）：**
- 协议：`HTTP`
- 服务器：`localhost`
- 端口：`5002`

### 方式二：SOCKS5 直接连接

启动后，Docker 会暴露 `5001` 端口作为 SOCKS5 代理入口：

```bash
# cURL 使用 SOCKS5
curl --socks5 localhost:5001 https://api.ipify.org?format=json

# 设置环境变量（全局生效）
export ALL_PROXY=socks5://localhost:5001

# Python 使用 SOCKS5
pip install requests[socks]
```

**带认证的 SOCKS5：**
```bash
# 启用认证后（见下方配置）
curl --socks5 proxyuser:proxypass@localhost:5001 https://api.ipify.org

export ALL_PROXY=socks5://proxyuser:proxypass@localhost:5001
```

### 方式二：API 获取代理列表

```python
import requests

# 获取最快的 10 个可用代理
response = requests.get('http://localhost:5000/api/proxies?working=true&limit=10')
proxies = response.json()['proxies']

# 使用第一个代理
if proxies:
    proxy = proxies[0]
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    
    # 在你的请求中使用
    response = requests.get(
        'https://target-site.com',
        proxies={'http': proxy_url, 'https': proxy_url}
    )
```

### cURL 示例

```bash
# 获取最快代理
FASTEST_PROXY=$(curl -s http://localhost:5000/api/proxies?working=true\&limit=1 | \
  jq -r '.proxies[0] | "\(.ip):\(.port)"')

# 使用代理
curl -x http://$FASTEST_PROXY https://api.ipify.org?format=json
```

### 浏览器配置

**Chrome/Firefox 扩展：**
1. 安装 [SwitchyOmega](https://chrome.google.com/webstore/detail/proxy-switchyomega/padekgcemlokbadohgkifijomclgjgif)
2. 新建代理情景模式
3. 协议选择 `SOCKS5`
4. 服务器：`localhost`，端口：`5001`
5. 保存并应用

**系统代理设置：**
- **Windows**: 设置 > 网络和 Internet > 代理 > 手动设置代理
- **macOS**: 系统偏好设置 > 网络 > 高级 > 代理 > SOCKS 代理
- **Linux**: 设置 > 网络 > 网络代理

## 📝 日志查看

```bash
# 实时查看日志
docker logs -f proxy-manager

# 查看最近 100 行
docker logs --tail 100 proxy-manager

# 导出日志
docker logs proxy-manager > proxy-manager.log
```

## ⚠️ 注意事项

1. **免费代理限制**: 免费代理稳定性有限，建议用于测试/开发场景
2. **使用政策**: 请遵守 [GitHub 合理使用政策](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)
3. **生产环境**: 生产使用建议搭配代理验证和故障转移逻辑
4. **隐私安全**: 不要通过免费代理传输敏感信息

## 🛠️ 故障排除

### 容器无法启动
```bash
# 检查端口占用
docker ps | grep 5000
lsof -i :5000

# 查看容器日志
docker-compose logs
```

### 代理获取失败
```bash
# 检查网络连接
docker exec proxy-manager curl -I https://cdn.jsdelivr.net

# 手动测试 API
curl http://localhost:5000/api/stats
```

### 测速结果为空
- 增加 `TEST_COUNT` 数量
- 增加 `TIMEOUT` 超时时间
- 检查网络是否能访问目标测试站点

## 📄 许可证

本项目基于 [Proxifly](https://github.com/proxifly/free-proxy-list) 的免费代理列表构建，请遵守原项目的许可条款。
