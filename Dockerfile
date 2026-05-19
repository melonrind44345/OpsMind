# OpsMind — Multi-stage Production Image
# ============================================================================
# Stage 1: Build virtualenv with all dependencies
# Stage 2: Minimal runtime image
#
# Build:
#   docker build -t opsmind:latest .
#
# Run:
#   docker run --rm opsmind:latest --version
#   docker run --rm opsmind:latest pipeline legacy-centos --method mock
# ============================================================================

# ---- Build stage ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /build
WORKDIR /build

RUN pip install --upgrade pip setuptools wheel \
    && pip install --target=/install .

# ---- Runtime stage ----
FROM python:3.11-slim

LABEL org.opencontainers.image.title="OpsMind"
LABEL org.opencontainers.image.description="Ansible-Driven Modernization Assessment Platform"
LABEL org.opencontainers.image.source="https://github.com/melonrind44345/OpsMind"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /install /usr/local/lib/python3.11/site-packages/

# Create non-root user
RUN useradd -m -s /bin/bash opsmind
USER opsmind
WORKDIR /home/opsmind

ENTRYPOINT ["opsmind"]
CMD ["--help"]
