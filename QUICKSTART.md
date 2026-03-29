# Proxy Manager - 快速配置指南

## 🚀 启动服务

```bash
cd /home/admin/openclaw/workspace/proxy-manager
./start.sh
```

访问 Web 面板：**http://localhost:5000**

---

## 📋 端口规划

| 端口 | 用途 | 说明 |
|------|------|------|
| `5000` | Web 管理面板 | 配置和监控界面 |
| `5001` | SOCKS5 入站 | 本机服务通过 SOCKS5 连接 |
| `5002` | HTTP/HTTPS 入站 | v2rayN 风格 HTTP 代理 |

---

## 🔌 配置入站代理

### 方式一：Web 面板配置（推荐）

#### 1. SOCKS5 入站配置（端口 5001）

在 Web 面板的「入站代理配置」区域：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 启用 SOCKS5 | 开启/关闭 SOCKS5 服务 | 启用 |
| 端口 | SOCKS5 监听端口 | 5001 |
| 启用认证 | 是否需要用户名密码 | 禁用 |
| 用户名 | 认证用户名 | proxyuser |
| 密码 | 认证密码 | proxypass |

**操作步骤：**
1. 修改配置（如端口 `5001` → `10800`）
2. 启用认证并设置用户名/密码
3. 点击「💾 保存配置」
4. 点击「🔄 重启服务」使配置生效
5. 点击「📋 复制连接信息」获取连接字符串

**连接格式：**
```
# 无认证
socks5://localhost:5001

# 有认证
socks5://username:password@localhost:5001
```

#### 2. HTTP/HTTPS 入站配置（端口 5002，v2rayN 风格）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 启用 HTTP 代理 | 开启/关闭 HTTP 服务 | 启用 |
| 端口 | HTTP 监听端口 | 5002 |
| 启用认证 | 是否需要用户名密码 | 禁用 |
| 用户名 | 认证用户名 | proxyuser |
| 密码 | 认证密码 | proxypass |

**操作步骤：**
1. 修改配置（如端口 `5002` → `8080`）
2. 启用认证并设置用户名/密码
3. 点击「💾 保存配置」
4. 点击「🔄 重启服务」使配置生效
5. 点击「📋 复制连接信息」获取连接字符串

**连接格式：**
```
# 无认证
http://localhost:5002

# 有认证
http://username:password@localhost:5002
```

---

### 方式二：配置文件

#### SOCKS5 配置
编辑 `data/socks5_config.json`：
```json
{
  "enabled": true,
  "port": 5001,
  "auth_enabled": false,
  "username": "proxyuser",
  "password": "proxypass"
}
```

#### HTTP 代理配置
编辑 `data/http_proxy_config.json`：
```json
{
  "enabled": true,
  "port": 5002,
  "auth_enabled": false,
  "username": "proxyuser",
  "password": "proxypass"
}
```

然后重启容器：
```bash
docker compose restart
```

---

## 🔗 使用代理

### SOCKS5 代理（端口 5001）

**连接格式：**
```
# 无认证
socks5://localhost:5001

# 有认证
socks5://username:password@localhost:5001
```

**cURL 测试：**
```bash
curl --socks5 localhost:5001 https://api.ipify.org?format=json
```

**环境变量：**
```bash
export ALL_PROXY=socks5://localhost:5001
```

**浏览器扩展（SwitchyOmega）：**
- 协议：SOCKS5
- 服务器：localhost
- 端口：5001

---

### HTTP/HTTPS 代理（端口 5002，v2rayN 风格）

**连接格式：**
```
# 无认证
http://localhost:5002

# 有认证
http://username:password@localhost:5002
```

**cURL 测试：**
```bash
curl -x http://localhost:5002 https://api.ipify.org?format=json
```

**环境变量：**
```bash
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002
```

**v2rayN 配置：**
1. 打开 v2rayN → 工具 → 全局选项
2. HTTP 代理：`localhost`
3. 端口：`5002`
4. 协议：`HTTP`
5. 保存

**Windows 系统代理：**
- 设置 → 网络和 Internet → 代理
- 地址：`localhost`
- 端口：`5002`

**浏览器扩展（SwitchyOmega）：**
- 协议：HTTP
- 服务器：`localhost`
- 端口：5002

---

## 📊 配置出站代理

在 Web 面板的「配置选项」区域：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 代理类型 | 获取的代理类型 | 全部 |
| 国家/地区 | 按地区筛选 | 全部国家 |
| 测试数量 | 每次测速的代理数量 | 15 |
| 自动测速间隔 | 后台重新测速的间隔（秒） | 60 |

**操作步骤：**
1. 修改配置
2. 点击「📥 获取代理」从 Proxifly 拉取最新代理
3. 点击「🚀 开始测速」测试代理延迟
4. 点击「💾 保存配置」保存设置

---

## 🔒 安全建议

1. **启用认证**：如果 Docker 暴露在公网，务必启用认证
2. **修改默认密码**：不要使用默认的 `proxyuser:proxypass`
3. **限制访问**：使用防火墙限制只有信任的 IP 可以访问
4. **使用 HTTPS**：生产环境建议配置反向代理（如 Nginx）启用 HTTPS

---

## 🛠️ 故障排除

### 配置不生效
1. 确认已点击「保存配置」
2. 确认已点击「重启服务」
3. 检查 `data/` 目录下的配置文件是否正确
4. 查看日志：`docker compose logs -f`

### 无法连接代理
1. 确认服务已启动：`docker compose ps`
2. 确认端口未被占用：`lsof -i :5001`
3. 确认防火墙允许连接
4. 在 Web 面板查看代理状态

### 代理速度慢
1. 在 Web 面板点击「🚀 开始测速」
2. 选择延迟更低的代理
3. 调整「自动测速间隔」更频繁地更新
4. 筛选特定国家的代理

---

## 📝 常用命令

```bash
# 启动服务
./start.sh

# 停止服务
./stop.sh

# 查看日志
docker compose logs -f

# 查看代理状态
curl http://localhost:5000/api/stats

# 查看 SOCKS5 配置
curl http://localhost:5000/api/config/socks5

# 查看 HTTP 代理配置
curl http://localhost:5000/api/config/http-proxy

# 测试 HTTP 代理（端口 5002）
curl -x http://localhost:5002 https://api.ipify.org

# 测试 SOCKS5 代理（端口 5001）
curl --socks5 localhost:5001 https://api.ipify.org
```

---

## 📖 更多信息

- 完整文档：`README.md`
- 更新日志：`CHANGELOG.md`
- GitHub: https://github.com/proxifly/free-proxy-list
