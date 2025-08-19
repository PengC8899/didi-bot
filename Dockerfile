# 使用官方Python运行时作为父镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 复制项目文件
COPY orderbot/pyproject.toml ./orderbot/
COPY orderbot/src ./orderbot/src/
COPY orderbot/__init__.py ./orderbot/
COPY orderbot/__main__.py ./orderbot/
COPY healthcheck.py ./

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -e ./orderbot

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# 创建数据目录和日志目录
RUN mkdir -p /app/data /app/images /app/logs \
    && chown -R app:app /app/data /app/images /app/logs

# 暴露端口（如果将来需要webhook）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=5 \
    CMD python healthcheck.py || exit 1

# 启动命令
CMD ["python", "-m", "orderbot"]

# 添加标签用于监控和管理
LABEL maintainer="orderbot-team" \
      version="1.0" \
      description="Telegram Order Bot with enhanced stability" \
      monitoring.enabled="true"