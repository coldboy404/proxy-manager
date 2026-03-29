# Proxy Manager - 更新日志

## v2.0 - Web 面板配置功能 (2026-03-19)

### ✨ 新增功能

#### 🎨 Web 面板配置界面
- ✅ **SOCKS5 入站配置**（端口 5001）
  - 启用/禁用开关
  - 端口配置（默认 5001，可自定义）
  - 认证开关（用户名/密码）
  - 实时状态显示
  - 连接数统计
  - 一键复制连接信息

- ✅ **HTTP/HTTPS 入站配置**（端口 5002，v2rayN 风格）
  - 启用/禁用开关
  - 端口配置（默认 5002，可自定义）
  - 认证开关（用户名/密码）
  - 实时状态显示
  - 请求数统计
  - 一键复制连接信息

#### 🔧 后端 API
- `GET /api/config/socks5` - 获取 SOCKS5 配置
- `POST /api/config/socks5` - 保存 SOCKS5 配置
- `POST /api/restart/socks5` - 重启 SOCKS5 服务
- `GET /api/config/http-proxy` - 获取 HTTP 代理配置
- `POST /api/config/http-proxy` - 保存 HTTP 代理配置
- `POST /api/restart/http-proxy` - 重启 HTTP 代理服务

#### 📁 配置文件
- `data/socks5_config.json` - SOCKS5 配置
- `data/http_proxy_config.json` - HTTP 代理配置

### 🚀 使用方式

#### 1. 通过 Web 面板配置（推荐）
访问 `http://localhost:5000`，在「入站代理配置」区域：

**SOCKS5 配置：**
- 启用/禁用 SOCKS5 服务
- 修改端口（如 1080 → 10800）
- 启用认证并设置用户名/密码
- 点击「保存配置」
- 点击「重启服务」使配置生效

**HTTP 代理配置：**
- 启用/禁用 HTTP 代理服务
- 修改端口（如 5001 → 8080）
- 启用认证并设置用户名/密码
- 点击「保存配置」
- 点击「重启服务」使配置生效

#### 2. 连接信息格式

**SOCKS5（端口 5001）：**
```
# 无认证
socks5://localhost:5001

# 有认证
socks5://username:password@localhost:5001
```

**HTTP/HTTPS（端口 5002）：**
```
# 无认证
http://localhost:5002

# 有认证
http://username:password@localhost:5002
```

### 🔌 使用示例

#### cURL 测试
```bash
# SOCKS5（端口 5001）
curl --socks5 localhost:5001 https://api.ipify.org

# HTTP 代理（端口 5002）
curl -x http://localhost:5002 https://api.ipify.org
```

#### 环境变量
```bash
# SOCKS5
export ALL_PROXY=socks5://localhost:5001

# HTTP 代理
export HTTP_PROXY=http://localhost:5002
export HTTPS_PROXY=http://localhost:5002
```

#### v2rayN 配置
1. 打开 v2rayN → 工具 → 全局选项
2. HTTP 代理：`localhost`
3. 端口：`5002`（或你配置的端口）
4. 协议：`HTTP`
5. 保存

### 📊 Web 面板功能

#### 实时监控
- 总代理数、可用代理数、平均延迟
- SOCKS5 连接数
- HTTP 代理请求数
- 最后更新时间

#### 出站代理配置
- 代理类型：全部/HTTP/HTTPS/SOCKS4/SOCKS5
- 国家/地区筛选
- 测试数量：每次测速的代理数量
- 自动测速间隔：后台重新测速的间隔

### ⚙️ 环境变量（可选）

首次启动时可通过环境变量设置默认值：

```yaml
# docker-compose.yml
environment:
  # SOCKS5 默认配置
  - SOCKS5_ENABLED=true
  - SOCKS5_PORT=1080
  - SOCKS5_AUTH=false
  - SOCKS5_USER=proxyuser
  - SOCKS5_PASS=proxypass
  
  # HTTP 代理默认配置
  - HTTP_PROXY_ENABLED=true
  - HTTP_PROXY_PORT=5001
  - HTTP_PROXY_AUTH=false
  - HTTP_PROXY_USER=proxyuser
  - HTTP_PROXY_PASS=proxypass
```

**注意：** 通过 Web 面板保存的配置会覆盖环境变量设置。

### 🔄 配置持久化

所有配置保存在 `data/` 目录：
```
data/
├── socks5_config.json       # SOCKS5 配置
├── http_proxy_config.json   # HTTP 代理配置
└── config.json              # 出站代理配置
```

挂载卷持久化：
```yaml
volumes:
  - ./data:/app/data
```

### 🚨 注意事项

1. **修改端口后需要重启服务**：保存配置后点击「重启服务」按钮
2. **当前连接会断开**：重启服务时现有连接会断开
3. **配置自动保存**：保存后配置写入文件，重启容器后依然有效
4. **认证安全**：建议启用认证以防止未授权访问

### 🐛 已知问题

- 重启服务功能目前仅重新加载配置，完全重启需要重启容器
- 未来版本会添加完整的服务重启功能

---

## v1.0 - 初始版本

### 功能
- 自动从 Proxifly 获取代理
- 智能测速和延迟排序
- 后台自动轮询
- Web 管理面板
- SOCKS5 入站代理
- HTTP/HTTPS 入站代理
