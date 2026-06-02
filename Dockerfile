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

# Create a virtualenv so that entry points (console_scripts) are captured
# together with all dependencies in a single, relocatable tree.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . /build
WORKDIR /build

# Install the package into the venv — this places:
#   packages   → /opt/venv/lib/python3.11/site-packages/
#   entrypoint → /opt/venv/bin/opsmind
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# ---- Runtime stage ----
FROM python:3.11-slim

LABEL org.opencontainers.image.title="OpsMind"
LABEL org.opencontainers.image.description="Ansible-Driven Modernization Assessment Platform"
LABEL org.opencontainers.image.source="https://github.com/melonrind44345/OpsMind"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

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

# Verify the binary resolves (fail loudly at build time, not at run time).
RUN opsmind --version

# Create non-root user
RUN useradd -m -s /bin/bash opsmind
USER opsmind
WORKDIR /home/opsmind

ENTRYPOINT ["opsmind"]
CMD ["--help"]
