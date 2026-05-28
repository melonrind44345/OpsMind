"""Complexity and resource sizing evaluator."""

from opsmind.schemas.assessment import (
    ComplexityAssessment,
    ComplexityLevel,
    MigrationStrategy,
    ResourceSizing,
)
from opsmind.schemas.discovery import UnifiedDiscoveryModel


class ComplexityEvaluator:
    """Evaluates migration complexity and recommends resource sizing."""

    def evaluate(
        self, discovery_data: UnifiedDiscoveryModel, detail_level: str = "detailed"
    ) -> "ComplexityEvaluationResult":
        """Perform complexity assessment.

        Args:
            discovery_data: Unified discovery data
            detail_level: Assessment detail level

        Returns:
            Object containing ComplexityAssessment, ResourceSizing, MigrationStrategy
        """
        level, score, factors = self._assess_complexity(discovery_data)
        sizing = self._recommend_sizing(discovery_data)
        strategy = self._recommend_strategy(level, discovery_data)

        breakdown_lines = [f"Complexity score: {score:.1f}/100", f"Level: {level.value}"]
        for factor, fscore in sorted(factors.items(), key=lambda x: -x[1]):
            breakdown_lines.append(f"  - {factor}: {fscore:.1f}")

        assessment = ComplexityAssessment(
            level=level,
            score=score,
            factors=factors,
            breakdown="\n".join(breakdown_lines),
            estimated_effort_days=self._estimate_effort(level, discovery_data),
            skill_requirements=self._identify_skills(level, discovery_data),
        )

        return ComplexityEvaluationResult(
            assessment=assessment,
            sizing=sizing,
            strategy=strategy,
        )

    def _assess_complexity(self, data: UnifiedDiscoveryModel) -> tuple[ComplexityLevel, float, dict[str, float]]:
        """Assess overall migration complexity."""
        factors: dict[str, float] = {}

        # OS factor
        os_name = data.software.os_name.lower()
        os_version = data.software.os_version
        if "centos" in os_name and os_version.startswith("6"):
            factors["Legacy OS"] = 80.0
        elif "windows" in os_name:
            factors["Windows platform"] = 90.0
        elif "centos" in os_name and os_version.startswith("7"):
            factors["Aging OS"] = 50.0
        else:
            factors["Modern OS"] = 20.0

        # Service factor
        critical_services = [s for s in data.software.services if s.state == "running"]
        if len(critical_services) > 10:
            factors["Many running services"] = 70.0
        elif len(critical_services) > 5:
            factors["Moderate services"] = 40.0
        else:
            factors["Few services"] = 10.0

        # Database factor
        db_keywords = ["mysql", "postgres", "mariadb", "mongodb", "oracle", "mssql"]
        has_db = any(any(kw in s.name.lower() for kw in db_keywords) for s in data.software.services)
        if has_db:
            factors["Database services present"] = 50.0

        # Package count factor
        pkg_count = len(data.software.packages)
        if pkg_count > 500:
            factors[f"Many packages ({pkg_count})"] = 60.0
        elif pkg_count > 200:
            factors[f"Moderate packages ({pkg_count})"] = 30.0
        else:
            factors[f"Few packages ({pkg_count})"] = 10.0

        # Disk factor
        disk_count = len(data.hardware.disks)
        if disk_count > 5:
            factors[f"Many mount points ({disk_count})"] = 50.0
        elif disk_count > 2:
            factors["Multiple mount points"] = 30.0

        # Calculate weighted score
        weights = {
            "Legacy OS": 0.25,
            "Aging OS": 0.15,
            "Modern OS": 0.05,
            "Windows platform": 0.30,
            "Many running services": 0.20,
            "Moderate services": 0.10,
            "Few services": 0.05,
            "Database services present": 0.15,
            "Many packages": 0.10,
            "Moderate packages": 0.05,
            "Few packages": 0.02,
            "Many mount points": 0.10,
            "Multiple mount points": 0.05,
        }

        total_weight = 0.0
        weighted_sum = 0.0
        for factor_name, factor_score in factors.items():
            w = weights.get(factor_name, 0.05)
            weighted_sum += factor_score * w
            total_weight += w

        raw_score = weighted_sum / max(total_weight, 0.01)

        # Determine level
        if raw_score < 25:
            level = ComplexityLevel.SIMPLE
        elif raw_score < 50:
            level = ComplexityLevel.MODERATE
        elif raw_score < 75:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.BLOCKER

        return level, raw_score, factors

    def _recommend_sizing(self, data: UnifiedDiscoveryModel) -> ResourceSizing:
        """Recommend container resource sizing based on current usage."""
        hw = data.hardware

        # CPU: use current cores as baseline
        cpu = max(0.5, hw.cpu.cores * 0.5)

        # Memory: use 75% of current as baseline
        mem = max(0.5, hw.memory.total_gb * 0.75)

        # Storage: sum of all disks * overhead factor
        storage = max(10.0, sum(d.total_gb for d in hw.disks) * 0.3)

        # Replicas: default to 1, 2 for critical services
        replicas = 1

        rationale = (
            f"Sizing based on current hardware: {hw.cpu.cores} cores, "
            f"{hw.memory.total_gb}GB memory. "
            f"Container overhead estimated at ~25%. "
        )

        optimizations = []
        if mem > 32:
            optimizations.append("Consider memory limits to prevent resource waste")
        if cpu > 8:
            optimizations.append("CPU requests can be set lower than limits")
        optimizations.append("Use HorizontalPodAutoscaler for dynamic scaling")

        return ResourceSizing(
            cpu_cores=round(cpu, 1),
            memory_gb=round(mem, 1),
            storage_gb=round(storage, 1),
            replicas=replicas,
            rationale=rationale,
            optimizations=optimizations,
        )

    def _recommend_strategy(self, level: ComplexityLevel, data: UnifiedDiscoveryModel) -> MigrationStrategy:
        """Recommend migration strategy."""
        sw = data.software
        os_lower = sw.os_name.lower()

        if "centos" in os_lower and sw.os_version.startswith("6"):
            strategy_type = "refactor"
            phases = [
                {"phase": 1, "name": "Assessment", "duration": "1-2 days"},
                {"phase": 2, "name": "OS Upgrade", "duration": "2-3 days"},
                {"phase": 3, "name": "Application Refactor", "duration": "3-5 days"},
                {"phase": 4, "name": "Container Build", "duration": "1-2 days"},
                {"phase": 5, "name": "Testing & Validation", "duration": "2-3 days"},
            ]
            risks = [
                "Legacy OS EOL - no security patches",
                "Application compatibility with newer base images",
                "Data migration risks",
            ]
        elif "windows" in os_lower:
            strategy_type = "rearchitect"
            phases = [
                {"phase": 1, "name": "Assessment & Planning", "duration": "3-5 days"},
                {"phase": 2, "name": "Code Porting", "duration": "5-10 days"},
                {"phase": 3, "name": "Container Build", "duration": "2-3 days"},
                {"phase": 4, "name": "Testing", "duration": "3-5 days"},
            ]
            risks = [
                "Windows container compatibility",
                ".NET Framework vs .NET Core migration",
                "Licensing implications",
            ]
        else:
            strategy_type = "rehost"
            phases = [
                {"phase": 1, "name": "Container Build", "duration": "1 day"},
                {"phase": 2, "name": "Configuration Migration", "duration": "1 day"},
                {"phase": 3, "name": "Testing", "duration": "1-2 days"},
                {"phase": 4, "name": "Cutover", "duration": "0.5 day"},
            ]
            risks = ["Minimal risks for modern OS"]

        return MigrationStrategy(
            strategy_type=strategy_type,
            phases=phases,
            estimated_duration_days=sum(p["duration"] for p in phases if isinstance(p.get("duration"), int)) or None,  # type: ignore[misc]
            risks=risks,
            rollback_strategy="Keep original system intact; redirect traffic via DNS change",
        )

    def _estimate_effort(self, level: ComplexityLevel, data: UnifiedDiscoveryModel) -> int:
        """Estimate effort in days."""
        base_estimates = {
            ComplexityLevel.SIMPLE: 3,
            ComplexityLevel.MODERATE: 7,
            ComplexityLevel.COMPLEX: 14,
            ComplexityLevel.BLOCKER: 30,
        }
        return base_estimates.get(level, 7)

    def _identify_skills(self, level: ComplexityLevel, data: UnifiedDiscoveryModel) -> list[str]:
        """Identify required skills."""
        skills = ["Docker", "Container orchestration basics"]
        if level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX, ComplexityLevel.BLOCKER):
            skills.extend(["Linux administration", "Networking", "Security hardening"])
        if level == ComplexityLevel.COMPLEX:
            skills.extend(["Kubernetes", "CI/CD pipeline design"])
        if level == ComplexityLevel.BLOCKER:
            skills.extend(["Application refactoring", "Legacy system modernization"])
        return skills


class ComplexityEvaluationResult:
    """Container for complexity evaluation outputs."""

    def __init__(
        self,
        assessment: ComplexityAssessment,
        sizing: ResourceSizing,
        strategy: MigrationStrategy,
    ) -> None:
        self.assessment = assessment
        self.sizing = sizing
        self.strategy = strategy
