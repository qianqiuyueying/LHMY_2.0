FROM python:3.13-slim

# 避免 Python 输出缓存，便于容器日志查看
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 系统依赖（MySQL 客户端编译依赖等）
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev \
  && rm -rf /var/lib/apt/lists/*

# uv（用于依赖安装）
RUN pip install --no-cache-dir uv==0.9.18

# 先拷贝依赖描述文件以利用缓存
COPY pyproject.toml uv.lock /app/

# 安装生产依赖到 /app/.venv
RUN uv sync --frozen --no-dev

# 让容器内默认使用 venv 的可执行文件（uvicorn 等）
ENV PATH="/app/.venv/bin:${PATH}"

COPY backend/ /app

EXPOSE 8000
