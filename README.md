# Proxy Manager

一个带 Web 面板的代理池管理项目：
自动拉取代理、测速筛选、按延迟排序，并对外提供统一的 **SOCKS5 入站** 和 **HTTP/HTTPS 入站**。

适合这种场景：
- 想快速收集一批可用代理
- 想通过 Web 面板查看代理池状态
- 想把代理池统一暴露给其他程序使用
- 想用固定端口接入 SOCKS5 / HTTP 代理

---

## 功能特性

- 自动拉取代理列表
- 支持 HTTP / HTTPS / SOCKS4 / SOCKS5
- 支持按国家/地区筛选
- 自动测速并按延迟排序
- Web 管理面板
- SOCKS5 入站代理：`5001`
- HTTP/HTTPS 入站代理：`5002`
- 配置与数据本地持久化

---

## 默认端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Web 面板 | `5000` | 管理界面与 API |
| SOCKS5 入站 | `5001` | 给其他程序走 SOCKS5 |
| HTTP/HTTPS 入站 | `5002` | 给其他程序走 HTTP 代理 |

---

## 快速开始

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 按需修改端口、认证和自动测速参数。


### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/coldboy404/proxy-manager.git
cd proxy-manager
docker compose up -d --build
```

启动后访问：

- Web 面板：<http://localhost:5000>
- SOCKS5：`localhost:5001`
- HTTP/HTTPS：`localhost:5002`

停止：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

---

### 方式二：一键脚本

```bash
cd /root/.openclaw/workspace/proxy-manager
./start.sh
```

停止：

```bash
./stop.sh
```

---

### 方式三：本地运行（Python 3.11+）

```bash
pip install -r requirements.txt
python app/proxy_manager.py
```

---

## 首次使用

### 1. 打开面板

访问：

```text
http://localhost:5000
```

### 2. 获取代理

在面板中点击：

- **获取代理**

### 3. 开始测速

点击：

- **开始测速**

### 4. 连接代理池

#### SOCKS5

```bash
curl --socks5 localhost:5001 https://api.ipify.org?format=json
```

```bash
export ALL_PROXY=socks5://localhost:5001
```

#### HTTP/HTTPS

```bash
curl -x http://localhost:5002 https://api.ipify.org?format=json
```

```bash
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002
```

---

## Docker Compose 配置说明

默认 `docker-compose.yml` 会暴露：

```yaml
ports:
  - "5000:5000"
  - "5001:5001"
  - "5002:5002"
```

并持久化：

```yaml
volumes:
  - ./data:/app/data
  - ./logs:/app/logs
```

这表示：
- 配置保存在宿主机 `./data`
- 日志保存在宿主机 `./logs`
- 重建容器后数据不会丢

---

## 环境变量

### 基础配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POLL_INTERVAL` | `300` | 代理列表更新间隔（秒） |
| `TEST_INTERVAL` | `60` | 自动测速间隔（秒） |
| `TEST_COUNT` | `50` | 每次测速数量 |
| `TIMEOUT` | `10` | 超时（秒） |
| `TEST_URL` | `https://www.google.com` | 测试地址 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DATA_DIR` | `/app/data` | 数据目录 |

### SOCKS5 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOCKS5_ENABLED` | `true` | 是否启用 SOCKS5 |
| `SOCKS5_HOST` | `0.0.0.0` | 监听地址 |
| `SOCKS5_PORT` | `5001` | 监听端口 |
| `SOCKS5_AUTH` | `false` | 是否启用认证 |
| `SOCKS5_USER` | `proxyuser` | 用户名 |
| `SOCKS5_PASS` | `proxypass` | 密码 |

### HTTP 代理配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HTTP_PROXY_ENABLED` | `true` | 是否启用 HTTP 代理 |
| `HTTP_PROXY_HOST` | `0.0.0.0` | 监听地址 |
| `HTTP_PROXY_PORT` | `5002` | 监听端口 |
| `HTTP_PROXY_AUTH` | `false` | 是否启用认证 |
| `HTTP_PROXY_USER` | `proxyuser` | 用户名 |
| `HTTP_PROXY_PASS` | `proxypass` | 密码 |

---

## 常见自定义

### 修改 SOCKS5 端口到 1080

```yaml
environment:
  - SOCKS5_PORT=1080
ports:
  - "1080:1080"
```

### 修改 HTTP 端口到 5003

```yaml
environment:
  - HTTP_PROXY_PORT=5003
ports:
  - "5003:5003"
```

### 开启 SOCKS5 认证

```yaml
environment:
  - SOCKS5_AUTH=true
  - SOCKS5_USER=myuser
  - SOCKS5_PASS=mypassword
```

### 开启 HTTP 代理认证

```yaml
environment:
  - HTTP_PROXY_AUTH=true
  - HTTP_PROXY_USER=myuser
  - HTTP_PROXY_PASS=mypassword
```

---

## Web 面板说明

面板支持查看：

- 总代理数
- 可用代理数
- 平均延迟
- 已测试数量
- 当前筛选条件
- 代理列表

常见操作：

- 获取代理
- 开始测速
- 保存配置
- 刷新列表

---

## API 示例

### 查看统计

```bash
curl http://localhost:5000/api/stats
```

### 查看代理列表

```bash
curl http://localhost:5000/api/proxies
```

### 只看可用代理

```bash
curl "http://localhost:5000/api/proxies?working=true"
```

### 手动获取代理

```bash
curl -X POST http://localhost:5000/api/proxies/fetch \
  -H "Content-Type: application/json" \
  -d '{"type":"all","country":"US"}'
```

### 手动测速

```bash
curl -X POST http://localhost:5000/api/proxies/test \
  -H "Content-Type: application/json" \
  -d '{"count":15,"country":"US","protocol":"https"}'
```

### 查看 SOCKS5 状态

```bash
curl http://localhost:5000/api/socks5
```

### 查看 HTTP 代理状态

```bash
curl http://localhost:5000/api/http-proxy
```

---

## 目录结构

```text
proxy-manager/
├── app/                  # Flask 应用与核心逻辑
├── templates/            # Web 面板模板
├── data/                 # 本地配置与数据
├── logs/                 # 日志目录
├── docker-compose.yml    # Docker Compose 部署
├── Dockerfile            # 镜像构建文件
├── start.sh              # 启动脚本
├── stop.sh               # 停止脚本
└── README.md
```

---

## 数据目录

```text
data/
└── config.json
```

后续可扩展更多运行数据与历史记录。

---

## 故障排查

### 面板打不开

```bash
docker compose ps
docker compose logs -f
ss -lntp | grep -E '5000|5001|5002'
```

### 没有代理数据

先确认是否已执行：
- 获取代理
- 开始测速

### 代理很多但不可用

检查：
- `TIMEOUT` 是否太短
- 测试地址是否可访问
- 宿主机网络是否正常

---

## 适合接入的程序

- curl
- requests
- 浏览器代理扩展
- 其他支持 SOCKS5 / HTTP 代理的软件

---

## 仓库

- GitHub: <https://github.com/coldboy404/proxy-manager>
- Author: **coldboy404**
