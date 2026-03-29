# Proxy Manager - 端口规划与使用指南

## 📋 端口规划

| 端口 | 用途 | 协议 | 说明 |
|------|------|------|------|
| `5000` | Web 管理面板 | HTTP | 配置和监控界面 |
| `5001` | SOCKS5 入站 | SOCKS5 | 本机服务通过 SOCKS5 连接 |
| `5002` | HTTP/HTTPS 入站 | HTTP/HTTPS | v2rayN 风格本地代理 |

---

## 🎯 设计理念

### 清晰的端口分配
- **5000 系列**：入站代理服务
- **5000**：Web 管理（固定）
- **5001**：SOCKS5 入站（默认）
- **5002**：HTTP/HTTPS 入站（默认）

### 灵活的配置
所有入站代理的端口都可以在 Web 面板上自由修改：
- 可以改成任意未占用的端口（1-65535）
- 支持启用/禁用认证
- 配置实时生效（需重启服务）

---

## 🔌 入站代理工作流

```
┌─────────────────┐
│  本机其他服务    │
│  (浏览器/应用)   │
└────────┬────────┘
         │
         │ 请求
         ↓
┌─────────────────────────────────┐
│  Proxy Manager Docker 容器       │
│  ┌─────────────────────────┐   │
│  │  入站代理 (5001/5002)   │   │
│  │  - SOCKS5 (5001)        │   │
│  │  - HTTP/HTTPS (5002)    │   │
│  └───────────┬─────────────┘   │
│              │                  │
│              │ 自动选择         │
│              ↓                  │
│  ┌─────────────────────────┐   │
│  │  代理池（已测速排序）    │   │
│  │  - 从 Proxifly 获取      │   │
│  │  - 每 5 分钟更新          │   │
│  │  - 自动测速              │   │
│  └───────────┬─────────────┘   │
└──────────────│─────────────────┘
               │
               │ 出站请求
               ↓
      ┌────────────────┐
      │  目标网站/服务   │
      └────────────────┘
```

---

## 🚀 快速使用

### 1. 启动服务

```bash
cd /home/admin/openclaw/workspace/proxy-manager
./start.sh
```

### 2. 访问 Web 面板

打开浏览器访问：**http://localhost:5000**

### 3. 配置入站代理

在「入站代理配置」区域：

**SOCKS5 入站（5001）：**
- 启用 SOCKS5：`启用`
- 端口：`5001`（可修改）
- 启用认证：`禁用`（或启用并设置用户名密码）
- 点击「💾 保存配置」
- 点击「🔄 重启服务」

**HTTP/HTTPS 入站（5002）：**
- 启用 HTTP 代理：`启用`
- 端口：`5002`（可修改）
- 启用认证：`禁用`（或启用并设置用户名密码）
- 点击「💾 保存配置」
- 点击「🔄 重启服务」

### 4. 配置出站代理

在「配置选项」区域：
- 代理类型：`全部类型`（或指定 HTTP/HTTPS/SOCKS4/SOCKS5）
- 国家/地区：`全部国家`（或指定国家）
- 测试数量：`15`（每次测速的代理数量）
- 自动测速间隔：`60`（秒）

点击：
1. 「📥 获取代理」- 从 Proxifly 拉取最新代理
2. 「🚀 开始测速」- 测试代理延迟
3. 「💾 保存配置」- 保存设置

---

## 🔗 使用示例

### SOCKS5 入站（端口 5001）

#### cURL 测试
```bash
curl --socks5 localhost:5001 https://api.ipify.org?format=json
```

#### 环境变量（全局生效）
```bash
export ALL_PROXY=socks5://localhost:5001

# Python 示例
import requests
response = requests.get('https://api.ipify.org')
print(response.text)
```

#### 浏览器扩展（SwitchyOmega）
1. 安装 SwitchyOmega
2. 新建情景模式
3. 协议：`SOCKS5`
4. 服务器：`localhost`
5. 端口：`5001`
6. 保存并应用

#### 系统代理设置
**Windows:**
- 设置 → 网络和 Internet → 代理
- 手动设置代理：开
- 地址：`localhost`
- 端口：`5001`

**macOS:**
- 系统偏好设置 → 网络 → 高级 → 代理
- SOCKS 代理：`localhost:5001`

**Linux:**
- 设置 → 网络 → 网络代理
- SOCKS 主机：`localhost`
- 端口：`5001`

---

### HTTP/HTTPS 入站（端口 5002）

#### cURL 测试
```bash
curl -x http://localhost:5002 https://api.ipify.org?format=json
```

#### 环境变量（全局生效）
```bash
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002

# Python 示例
import requests
proxies = {
    'http': 'http://localhost:5002',
    'https': 'http://localhost:5002'
}
response = requests.get('https://api.ipify.org', proxies=proxies)
print(response.text)
```

#### v2rayN 配置
1. 打开 v2rayN
2. 工具 → 全局选项
3. HTTP 代理：
   - 地址：`localhost`
   - 端口：`5002`
   - 协议：`HTTP`
4. 保存

#### Windows 系统代理
- 设置 → 网络和 Internet → 代理
- 手动设置代理：开
- 地址：`localhost`
- 端口：`5002`

#### 浏览器扩展（SwitchyOmega）
1. 安装 SwitchyOmega
2. 新建情景模式
3. 协议：`HTTP`
4. 服务器：`localhost`
5. 端口：`5002`
6. 保存并应用

---

## ⚙️ 自定义端口

如果想修改默认端口（如 5001 → 10800，5002 → 8080）：

### 方式一：Web 面板（推荐）

1. 访问 http://localhost:5000
2. 在「入站代理配置」区域修改端口
3. 点击「💾 保存配置」
4. 点击「🔄 重启服务」

### 方式二：配置文件

**修改 SOCKS5 端口：**
编辑 `data/socks5_config.json`：
```json
{
  "enabled": true,
  "port": 10800,
  "auth_enabled": false,
  "username": "proxyuser",
  "password": "proxypass"
}
```

**修改 HTTP 代理端口：**
编辑 `data/http_proxy_config.json`：
```json
{
  "enabled": true,
  "port": 8080,
  "auth_enabled": false,
  "username": "proxyuser",
  "password": "proxypass"
}
```

然后重启：
```bash
docker compose restart
```

### 方式三：环境变量（首次启动）

编辑 `docker-compose.yml`：
```yaml
environment:
  # SOCKS5 端口
  - SOCKS5_PORT=10800
  
  # HTTP 代理端口
  - HTTP_PROXY_PORT=8080
```

然后重启：
```bash
docker compose down
docker compose up -d
```

---

## 🔒 启用认证

### 为什么需要认证？
如果 Docker 暴露在公网或局域网，启用认证可以防止未授权访问。

### 启用 SOCKS5 认证
1. Web 面板 → SOCKS5 入站配置
2. 启用认证：`启用`
3. 设置用户名和密码
4. 保存配置 → 重启服务

**连接格式：**
```
socks5://username:password@localhost:5001
```

### 启用 HTTP 代理认证
1. Web 面板 → HTTP/HTTPS 入站配置
2. 启用认证：`启用`
3. 设置用户名和密码
4. 保存配置 → 重启服务

**连接格式：**
```
http://username:password@localhost:5002
```

---

## 📊 监控与调试

### 查看连接状态
```bash
# 查看 SOCKS5 状态
curl http://localhost:5000/api/socks5

# 查看 HTTP 代理状态
curl http://localhost:5000/api/http-proxy

# 查看统计信息
curl http://localhost:5000/api/stats
```

### 查看日志
```bash
# 实时日志
docker compose logs -f

# 最近 100 行
docker compose logs --tail 100
```

### 测试连通性
```bash
# 测试 SOCKS5
curl --socks5 localhost:5001 --connect-timeout 5 https://api.ipify.org

# 测试 HTTP
curl -x http://localhost:5002 --connect-timeout 5 https://api.ipify.org
```

---

## 🛠️ 常见问题

### Q: 端口被占用怎么办？
A: 在 Web 面板修改端口，或编辑配置文件后重启。

### Q: 如何完全禁用某个入站代理？
A: 在 Web 面板将「启用」设置为「禁用」，保存并重启。

### Q: 配置后不生效？
A: 
1. 确认已点击「保存配置」
2. 确认已点击「重启服务」
3. 检查 `data/` 目录下的配置文件
4. 查看日志：`docker compose logs -f`

### Q: 代理速度慢？
A:
1. 在 Web 面板点击「🚀 开始测速」
2. 选择延迟更低的代理
3. 调整「自动测速间隔」更频繁地更新
4. 筛选特定国家的代理

### Q: 如何查看当前使用的出口代理？
A: 
```bash
# 通过代理访问 IP 查询网站
curl --socks5 localhost:5001 https://api.ipify.org?format=json
curl -x http://localhost:5002 https://api.ipify.org?format=json
```

---

## 📖 更多信息

- **完整文档**：`README.md`
- **快速指南**：`QUICKSTART.md`
- **更新日志**：`CHANGELOG.md`
- **项目地址**：https://github.com/proxifly/free-proxy-list

---

**最后更新**: 2026-03-19  
**版本**: v2.0
