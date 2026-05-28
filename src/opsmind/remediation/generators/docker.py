"""Docker artifact generator - creates Dockerfile, docker-compose, and build scripts."""

import os
from datetime import datetime

from opsmind.schemas.assessment import AssessmentResult, ComplexityLevel


class DockerGenerator:
    """Generates Docker configuration files based on assessment results."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir

    def generate(self, assessment_results: dict[str, AssessmentResult], optimize: str | None = None) -> list[str]:
        """Generate Docker artifacts for each host.

        Args:
            assessment_results: Assessment results per host
            optimize: Optimization target ('performance', 'size', 'cost')

        Returns:
            List of generated file paths
        """
        generated: list[str] = []

        for hostname, result in assessment_results.items():
            host_dir = os.path.join(self.output_dir, "docker", hostname)
            os.makedirs(host_dir, exist_ok=True)

            # Generate Dockerfile
            dockerfile = self._generate_dockerfile(result, optimize)
            df_path = os.path.join(host_dir, "Dockerfile")
            with open(df_path, "w") as f:
                f.write(dockerfile)
            generated.append(df_path)

            # Generate docker-compose.yml
            compose = self._generate_compose(hostname, result, optimize)
            compose_path = os.path.join(host_dir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(compose)
            generated.append(compose_path)

            # Generate .dockerignore
            ignore = self._generate_dockerignore(result)
            ignore_path = os.path.join(host_dir, ".dockerignore")
            with open(ignore_path, "w") as f:
                f.write(ignore)
            generated.append(ignore_path)

            # Generate build script
            script = self._generate_build_script(hostname)
            script_path = os.path.join(host_dir, "build.sh")
            with open(script_path, "w") as f:
                f.write(script)
            os.chmod(script_path, 0o755)
            generated.append(script_path)

        return generated

    def _generate_dockerfile(self, result: AssessmentResult, optimize: str | None = None) -> str:
        """Generate a Dockerfile based on the assessment."""
        is_legacy = result.feasibility.complexity in (
            ComplexityLevel.COMPLEX,
            ComplexityLevel.BLOCKER,
        )

        base_image = self._select_base_image(result)
        packages = self._estimate_packages(result)

        if optimize == "size":
            return f"""# OpsMind Generated Dockerfile - Size Optimized
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Host: {result.host}
# Strategy: {result.migration_strategy.strategy_type}

FROM {base_image} AS builder

RUN {"apt-get update && apt-get install -y --no-install-recommends " if "ubuntu" in base_image or "debian" in base_image else "yum install -y "} \\
    {packages} \\
    && rm -rf /var/lib/apt/lists/* /var/cache/yum/*

FROM {base_image}-slim

COPY --from=builder /usr /usr
COPY --from=builder /etc /etc

EXPOSE 80 443

CMD ["bash"]
"""
        else:
            return f"""# OpsMind Generated Dockerfile
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Host: {result.host}
# Strategy: {result.migration_strategy.strategy_type}
# Feasibility Score: {result.feasibility.overall_score}/100

FROM {base_image}

LABEL opsmind.host="{result.host}" \\
      opsmind.generated="{datetime.now().strftime("%Y-%m-%d")}" \\
      opsmind.version="0.1.0" \\
      description="Containerized {result.host} - {result.feasibility.complexity.value} migration"

# System dependencies
RUN {"apt-get update && apt-get install -y " if "ubuntu" in base_image or "debian" in base_image else "yum install -y "} \\
    {packages} \\
    && rm -rf /var/lib/apt/lists/* /var/cache/yum/*

# Application directory
WORKDIR /app

# Copy application files
COPY . .

# Expose common ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost/ || exit 1

LABEL opsmind.migration.risks="{"High" if is_legacy else "Low"}" \\
      opsmind.migration.effort="{result.complexity.estimated_effort_days} days"

CMD ["bash"]
"""

    def _generate_compose(self, hostname: str, result: AssessmentResult, optimize: str | None = None) -> str:
        """Generate docker-compose.yml."""
        sizing = result.resource_sizing

        return f"""# OpsMind Generated docker-compose.yml
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Host: {hostname}

version: "3.8"

services:
  {hostname}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {hostname}-container
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - {hostname}_data:/app/data
      - {hostname}_config:/app/config
    environment:
      - TZ=UTC
    deploy:
      resources:
        limits:
          cpus: "{sizing.cpu_cores}"
          memory: "{sizing.memory_gb}g"
        reservations:
          cpus: "{max(sizing.cpu_cores * 0.5, 0.5)}"
          memory: "{max(sizing.memory_gb * 0.5, 0.5)}g"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - opsmind_network

volumes:
  {hostname}_data:
    driver: local
  {hostname}_config:
    driver: local

networks:
  opsmind_network:
    driver: bridge
"""

    def _generate_dockerignore(self, result: AssessmentResult) -> str:
        """Generate .dockerignore file."""
        return """.git
.gitignore
*.md
__pycache__
*.pyc
*.pyo
.env
.gitkeep
node_modules
tests
docs
*.log
"""

    def _generate_build_script(self, hostname: str) -> str:
        """Generate build and run shell script."""
        return f"""#!/bin/bash
# OpsMind Build Script for {hostname}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

set -euo pipefail

echo "=== Building container for {hostname} ==="

# Build the image
docker compose build

# Run security scan (optional)
if command -v trivy &> /dev/null; then
    echo "Running security scan..."
    trivy image --severity HIGH,CRITICAL {hostname}:latest
fi

# Start the service
docker compose up -d

echo "=== Container started successfully ==="
echo "Run 'docker compose logs -f' to view logs"
echo "Run 'docker compose down' to stop"
"""

    def _select_base_image(self, result: AssessmentResult) -> str:
        """Select appropriate base image based on discovered OS."""
        strategy = result.migration_strategy.strategy_type
        complexity = result.feasibility.complexity

        base_images = {
            ("rehost", ComplexityLevel.SIMPLE): "ubuntu:22.04",
            ("rehost", ComplexityLevel.MODERATE): "ubuntu:22.04",
            ("refactor", ComplexityLevel.COMPLEX): "centos:7",
            ("refactor", ComplexityLevel.BLOCKER): "centos:7",
            ("rearchitect", ComplexityLevel.COMPLEX): "ubuntu:22.04",
        }
        return base_images.get((strategy, complexity), "ubuntu:22.04")

    def _estimate_packages(self, result: AssessmentResult) -> str:
        """Estimate required packages for container."""
        os_name = result.complexity.breakdown.lower()
        if "centos" in os_name or "redhat" in os_name or "rhel" in os_name:
            return "httpd mysql-server cronie openssh-clients curl wget"
        return "nginx mysql-server cron curl wget ca-certificates"
