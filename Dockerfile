# OpsMind — Multi-stage Production Image
# ============================================================================
# Stage 1: Build virtualenv with all dependencies
# Stage 2: Minimal runtime image
#
# [本地测试] 构建与运行（镜像仅存本地，不推送远程仓库）
#   docker build -t opsmind:latest .
#
# [本地测试] CLI 模式
#   docker run --rm opsmind:latest --version
#   docker run --rm opsmind:latest pipeline legacy-centos --method mock
#
# [本地测试] Web 服务模式（K8s 部署同此镜像）
#   docker run --rm -p 8080:8080 opsmind:latest web
#
# ⚠️ 本地测试请勿使用 --push，否则会尝试推送到 library/opsmind 导致 401 错误
# ============================================================================

# ---- Build stage ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a virtualenv so that entry points (console_scripts) are captured
# together with all dependencies in a single, relocatable tree.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . /build
WORKDIR /build

# Install the package into the venv — this places:
#   packages   → /opt/venv/lib/python3.11/site-packages/
#   entrypoint → /opt/venv/bin/opsmind
# [web] extra includes fastapi + uvicorn for the web API server.
RUN pip install --upgrade pip setuptools wheel \
    && pip install ".[web]"

# ---- Runtime stage ----
FROM python:3.11-slim

LABEL org.opencontainers.image.title="OpsMind"
LABEL org.opencontainers.image.description="Ansible-Driven Modernization Assessment Platform"
LABEL org.opencontainers.image.source="https://github.com/melonrind44345/OpsMind"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire virtualenv from the builder — one atomic layer that
# includes both site-packages AND the opsmind entry point.
COPY --from=builder /opt/venv /opt/venv

# Make venv binaries available on PATH.
# /usr/local/bin is already on PATH in the base image.
RUN ln -s /opt/venv/bin/opsmind /usr/local/bin/opsmind

# Verify the binary and all dependencies resolve at build time.
RUN opsmind --version
RUN python -c "import uvicorn, fastapi; print(f'uvicorn {uvicorn.__version__}, fastapi {fastapi.__version__}')"

# Create non-root user
RUN useradd -m -s /bin/bash opsmind
USER opsmind
WORKDIR /home/opsmind

# Default: show help (CLI mode).
# For K8s web deployment, override CMD to: ["opsmind", "web"]
ENTRYPOINT ["opsmind"]
CMD ["--help"]
