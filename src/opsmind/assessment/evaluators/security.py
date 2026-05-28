"""Security posture evaluator for containerization readiness."""

from opsmind.schemas.assessment import ComplexityAssessment, ComplexityLevel
from opsmind.schemas.discovery import UnifiedDiscoveryModel


class SecurityEvaluator:
    """Evaluates security readiness for containerization."""

    def evaluate(self, discovery_data: UnifiedDiscoveryModel) -> ComplexityAssessment:
        """Evaluate security posture.

        Args:
            discovery_data: Unified discovery data

        Returns:
            Security-focused complexity assessment
        """
        sec = discovery_data.security
        issues: int = 0
        factors: dict[str, float] = {}

        if not sec.ssh_config_secure:
            issues += 1
            factors["SSH Security"] = 40.0

        if sec.security_updates_count and sec.security_updates_count > 10:
            issues += 2
            factors["Pending Security Updates"] = 70.0

        if not sec.firewall_active:
            issues += 1
            factors["Firewall"] = 50.0

        if sec.selinux_enforcing is False:
            issues += 1
            factors["SELinux Disabled"] = 30.0

        open_port_count = len(sec.open_ports)
        if open_port_count > 5:
            factors[f"Exposed Ports ({open_port_count})"] = float(min(open_port_count * 5, 80))

        if not factors:
            factors["Security Posture"] = 10.0

        score = min(sum(factors.values()) / max(len(factors), 1), 100.0)

        if score < 20:
            level = ComplexityLevel.SIMPLE
        elif score < 45:
            level = ComplexityLevel.MODERATE
        elif score < 70:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.BLOCKER

        breakdown = (
            f"Security assessment score: {score:.1f}/100\n"
            f"Open ports: {open_port_count}\n"
            f"Firewall: {'Active' if sec.firewall_active else 'Inactive'}\n"
            f"SELinux: {'Enforcing' if sec.selinux_enforcing else 'Not enforcing'}\n"
            f"Pending security updates: {sec.security_updates_count or 'Unknown'}"
        )

        return ComplexityAssessment(
            level=level,
            score=round(score, 1),
            factors=factors,
            breakdown=breakdown,
        )
