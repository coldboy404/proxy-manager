FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY templates/ ./templates/

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
# Web 面板
EXPOSE 5000
# SOCKS5 入站代理
EXPOSE 5001
# HTTP/HTTPS 入站代理
EXPOSE 5002

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV POLL_INTERVAL=300
ENV TEST_INTERVAL=60
ENV TEST_COUNT=50
ENV TIMEOUT=10
ENV TEST_MODE=tcp
ENV AUTO_FETCH=true
ENV AUTO_TEST=true
ENV AUTO_FETCH_TYPE=all
ENV AUTO_FETCH_COUNTRIES=US,JP,SG
ENV AUTO_FETCH_LIMIT=50
ENV FETCH_LIMIT_PER_COUNTRY=50
ENV AUTO_TEST_PROTOCOL=
ENV AUTO_TEST_COUNT=50
ENV TEST_URL=https://www.google.com
ENV LOG_LEVEL=INFO

# 启动命令
CMD ["python", "-m", "app.server"]
