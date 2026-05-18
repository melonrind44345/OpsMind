"""Containerization feasibility evaluator.

Evaluates how suitable a system is for containerization across
multiple dimensions with weighted scoring.
"""

from typing import Any, Dict, List

from opsmind.schemas.assessment import (
    AssessmentDimension,
    ComplexityLevel,
    DimensionScore,
    FeasibilityReport,
    IssueDetail,
    RiskLevel,
)
from opsmind.schemas.discovery import UnifiedDiscoveryModel


class ContainerizationFeasibilityEvaluator:
    """Evaluates containerization feasibility based on discovered system data.

    Scoring dimensions:
    - Hardware compatibility (30%): CPU arch, memory, disk
    - Software support (30%): OS, packages, runtime compatibility
    - Configuration complexity (20%): Services, dependencies, state
    - Security baseline (20%): Firewall, SELinux, updates
    """

    SCORING_WEIGHTS = {
        AssessmentDimension.HARDWARE_COMPATIBILITY: 0.30,
        AssessmentDimension.SOFTWARE_SUPPORT: 0.30,
        AssessmentDimension.CONFIG_COMPLEXITY: 0.20,
        AssessmentDimension.SECURITY_BASELINE: 0.20,
    }

    def evaluate(self, discovery_data: UnifiedDiscoveryModel) -> FeasibilityReport:
        """Perform full feasibility evaluation.

        Args:
            discovery_data: Unified discovery data for a single host

        Returns:
            FeasibilityReport with scores, findings, and recommendations
        """
        hardware_score = self._assess_hardware(discovery_data)
        software_score = self._assess_software(discovery_data)
        config_score = self._assess_config_complexity(discovery_data)
        security_score = self._assess_security(discovery_data)

        dimension_scores = [
            hardware_score,
            software_score,
            config_score,
            security_score,
        ]

        overall_score = self._calculate_overall(dimension_scores)

        all_issues: List[IssueDetail] = []
        for ds in dimension_scores:
            all_issues.extend(self._findings_to_issues(ds, discovery_data))

        complexity = self._determine_complexity(overall_score, all_issues)
        risk = self._determine_risk(overall_score, all_issues)

        all_recommendations: List[str] = []
        for ds in dimension_scores:
            all_recommendations.extend(ds.recommendations)

        summary = self._generate_summary(overall_score, complexity, risk, discovery_data)

        return FeasibilityReport(
            overall_score=round(overall_score, 1),
            dimension_scores=dimension_scores,
            complexity=complexity,
            risk_level=risk,
            issues=all_issues,
            recommendations=all_recommendations[:10],
            summary=summary,
        )

    def _assess_hardware(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """Assess hardware compatibility for containerization."""
        score = 100.0
        findings: List[str] = []
        issues: List[str] = []
        recommendations: List[str] = []

        hw = data.hardware

        # CPU architecture check
        if hw.cpu.architecture in ("aarch64", "arm64"):
            score -= 5
            findings.append(f"CPU architecture: {hw.cpu.architecture}")
            recommendations.append("Verify container base images support ARM64 architecture")
        elif hw.cpu.architecture == "x86_64":
            findings.append("CPU architecture x86_64 - well supported in containers")
        else:
            score -= 20
            findings.append(f"Uncommon CPU architecture: {hw.cpu.architecture}")
            issues.append(f"CPU architecture '{hw.cpu.architecture}' may have limited container support")

        # CPU cores
        if hw.cpu.cores < 2:
            score -= 15
            issues.append("Less than 2 CPU cores - containers share host kernel")
            recommendations.append("Minimum 2 CPU cores recommended for containerized workloads")

        # Memory
        if hw.memory.total_gb < 2:
            score -= 20
            issues.append(f"Low memory: {hw.memory.total_gb}GB")
            recommendations.append("Minimum 2GB RAM recommended for containerized workloads")
        elif hw.memory.total_gb < 4:
            score -= 10
            findings.append(f"Memory: {hw.memory.total_gb}GB - adequate but consider upgrade")

        # Disk
        disks_with_space = [d for d in hw.disks if d.available_gb > 10]
        if not disks_with_space:
            score -= 15
            issues.append("No disk with >10GB available space")
            recommendations.append("Free up disk space for container images and volumes")

        # Network
        if not hw.network_interfaces:
            score -= 10
            findings.append("No network interfaces detected")

        return DimensionScore(
            dimension=AssessmentDimension.HARDWARE_COMPATIBILITY,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.HARDWARE_COMPATIBILITY],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_software(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """Assess software environment compatibility for containerization."""
        score = 100.0
        findings: List[str] = []
        issues: List[str] = []
        recommendations: List[str] = []

        sw = data.software

        # OS family assessment
        os_family = sw.os_family.lower()
        if os_family in ("debian", "ubuntu"):
            findings.append("Debian-based OS - good container support")
        elif os_family in ("redhat", "centos", "rhel"):
            findings.append("RHEL-based OS - good container support")
        elif os_family == "windows":
            score -= 30
            issues.append("Windows Server - requires Windows container support")
            recommendations.append("Consider Windows container or migrate to .NET Core/Linux")
        else:
            score -= 15
            findings.append(f"OS: {sw.os_family} - verify container compatibility")

        # OS version (older versions = more issues)
        os_version_parts = sw.os_version.split(".")
        try:
            major_ver = int(os_version_parts[0]) if os_version_parts else 0
        except ValueError:
            major_ver = 0

        if "centos" in sw.os_name.lower() and major_ver <= 6:
            score -= 15
            issues.append(f"CentOS {sw.os_version} - EOL, no official container images")
            recommendations.append("Upgrade OS before containerization or use compatible base image")
        elif "ubuntu" in sw.os_name.lower() and major_ver <= 16:
            score -= 10
            issues.append(f"Ubuntu {sw.os_version} - outdated, limited container support")
        elif "rhel" in sw.os_name.lower() and major_ver <= 7:
            score -= 10
            issues.append(f"RHEL {sw.os_version} - verify container compatibility")

        # Kernel version check
        kernel_parts = sw.kernel.split(".")
        try:
            kernel_major = int(kernel_parts[0]) if kernel_parts else 0
        except ValueError:
            kernel_major = 0

        if 0 < kernel_major < 3:
            score -= 20
            issues.append(f"Kernel {sw.kernel} - too old for container support")
        elif kernel_major < 4:
            score -= 10
            issues.append(f"Kernel {sw.kernel} - limited container support (cgroups v1)")

        # Container runtime check
        if any("docker" in s.name.lower() for s in sw.services):
            findings.append("Docker already installed - excellent container readiness")
        else:
            recommendations.append("Install container runtime (Docker/containerd)")

        # Service count
        if len(sw.services) > 20:
            score -= 5
            findings.append(f"{len(sw.services)} services running - complex service mesh")

        return DimensionScore(
            dimension=AssessmentDimension.SOFTWARE_SUPPORT,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.SOFTWARE_SUPPORT],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_config_complexity(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """Assess configuration complexity for containerization."""
        score = 100.0
        findings: List[str] = []
        issues: List[str] = []
        recommendations: List[str] = []

        hw = data.hardware
        sw = data.software

        # Disk count - multiple mount points increase complexity
        if len(hw.disks) > 3:
            score -= 10
            issues.append(f"{len(hw.disks)} mount points - complex volume mapping")
            recommendations.append("Map data volumes explicitly in docker-compose")

        # Zombie/non-critical services
        extra_services = [s for s in sw.services if s.name in ("sendmail", "rpcbind", "nfs", "autofs")]
        if extra_services:
            score -= 5
            findings.append(f"Legacy services: {[s.name for s in extra_services]}")
            recommendations.append("Evaluate necessity of legacy services before containerization")

        # SSH server
        ssh_services = [s for s in sw.services if "ssh" in s.name.lower()]
        if ssh_services:
            score -= 5
            findings.append("SSH server running - not needed in containers")

        # Database services
        db_services = [s for s in sw.services if s.name.lower() in ("mysqld", "postgresql", "mariadb", "mongod")]
        if db_services:
            score -= 5
            findings.append(f"Database services: {[s.name for s in db_services]}")
            recommendations.append("Separate database into its own container with persistent volume")

        return DimensionScore(
            dimension=AssessmentDimension.CONFIG_COMPLEXITY,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.CONFIG_COMPLEXITY],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_security(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """Assess security baseline for containerization."""
        score = 100.0
        findings: List[str] = []
        issues: List[str] = []
        recommendations: List[str] = []

        sec = data.security

        # Firewall check
        if not sec.firewall_active:
            score -= 15
            issues.append("No active firewall detected")
            recommendations.append("Enable firewall or use Docker's built-in network security")

        # SELinux
        if sec.selinux_enforcing is False:
            score -= 10
            findings.append("SELinux not enforcing")
            recommendations.append("Consider enabling SELinux for container security")
        elif sec.selinux_enforcing is True:
            findings.append("SELinux enforcing - good security posture")

        # OS updates
        if not sec.os_uptodate:
            score -= 10
            issues.append("System packages may be outdated")
            recommendations.append("Update system packages before container migration")

        # Security updates
        if sec.security_updates_count and sec.security_updates_count > 10:
            score -= 15
            issues.append(f"{sec.security_updates_count} pending security updates")
            recommendations.append(f"Apply {sec.security_updates_count} security updates before migration")

        # Open ports
        if len(sec.open_ports) > 10:
            score -= 5
            findings.append(f"{len(sec.open_ports)} open ports - review exposure")
            recommendations.append("Review and minimize exposed ports")

        return DimensionScore(
            dimension=AssessmentDimension.SECURITY_BASELINE,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.SECURITY_BASELINE],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _calculate_overall(self, dimension_scores: List[DimensionScore]) -> float:
        """Calculate weighted overall score."""
        total = 0.0
        for ds in dimension_scores:
            total += ds.score * ds.weight
        return total

    def _findings_to_issues(self, ds: DimensionScore, data: UnifiedDiscoveryModel) -> List[IssueDetail]:
        """Convert dimension findings to detailed issues."""
        issues: List[IssueDetail] = []
        for issue_text in ds.issues:
            severity = RiskLevel.HIGH if ds.score < 50 else RiskLevel.MEDIUM if ds.score < 75 else RiskLevel.LOW
            issues.append(IssueDetail(
                category=ds.dimension.value,
                severity=severity,
                title=issue_text[:80],
                description=issue_text,
                impact="May complicate or prevent containerization",
                recommendation="See recommendations above",
            ))
        return issues

    def _determine_complexity(self, score: float, issues: List[IssueDetail]) -> ComplexityLevel:
        """Determine overall complexity level."""
        if score >= 80:
            return ComplexityLevel.SIMPLE
        elif score >= 60:
            return ComplexityLevel.MODERATE
        elif score >= 40:
            return ComplexityLevel.COMPLEX
        return ComplexityLevel.BLOCKER

    def _determine_risk(self, score: float, issues: List[IssueDetail]) -> RiskLevel:
        """Determine overall risk level."""
        if score >= 80:
            return RiskLevel.LOW
        elif score >= 60:
            return RiskLevel.MEDIUM
        elif score >= 40:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    def _generate_summary(
        self, score: float, complexity: ComplexityLevel, risk: RiskLevel, data: UnifiedDiscoveryModel
    ) -> str:
        """Generate executive summary."""
        hostname = data.hardware.hostname
        os_info = f"{data.software.os_name} {data.software.os_version}"

        complexity_labels = {
            ComplexityLevel.SIMPLE: "straightforward",
            ComplexityLevel.MODERATE: "moderately complex",
            ComplexityLevel.COMPLEX: "complex",
            ComplexityLevel.BLOCKER: "currently not feasible",
        }

        return (
            f"Host '{hostname}' ({os_info}) has a containerization feasibility score of "
            f"{score:.1f}/100, indicating a {complexity_labels[complexity]} migration. "
            f"Risk level: {risk.value}. "
            f"{'The system is well-positioned for containerization.' if score >= 70 else 'Address identified issues before proceeding with containerization.'}"
        )
