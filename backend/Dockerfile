# 固定到已解析过的镜像 digest，避免部分网络环境下 “tag not found” 的瞬时波动
FROM python:3.13-slim-bookworm@sha256:0c5171fd1e80d3133604e1006aa5f788c5f020631537dd1e09edcbe874bb8192

# 避免 Python 输出缓存，便于容器日志查看
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 解决部分网络/代理环境访问 deb.debian.org 偶发 502：允许切换 apt 镜像源
# 如需自定义，可在 docker compose/build args 里传：
#   --build-arg DEBIAN_MIRROR=http://<your-mirror>/debian
#   --build-arg DEBIAN_SECURITY_MIRROR=http://<your-mirror>/debian-security
ARG DEBIAN_MIRROR=http://mirrors.aliyun.com/debian
ARG DEBIAN_SECURITY_MIRROR=http://mirrors.aliyun.com/debian-security

# 系统依赖（MySQL 客户端编译依赖等）
RUN set -eux; \
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
    sed -i "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    sed -i "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
  elif [ -f /etc/apt/sources.list ]; then \
    sed -i "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" /etc/apt/sources.list; \
    sed -i "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list; \
  fi; \
  apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update; \
  apt-get install -y --no-install-recommends --fix-missing build-essential default-libmysqlclient-dev; \
  rm -rf /var/lib/apt/lists/*

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
