"""OpsMind CLI - Main entry point with Typer + Rich."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from opsmind import __version__
from opsmind.core.engine import OpsMindEngine

app = typer.Typer(
    name="opsmind",
    help=f"[bold blue]OpsMind v{__version__}[/] - Ansible-Driven Modernization Platform",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)

_state: dict[str, Any] = {}


def _get_engine() -> OpsMindEngine:
    """Get or create the OpsMind engine."""
    if "engine" not in _state:
        _state["engine"] = OpsMindEngine()
    return _state["engine"]  # type: ignore[no-any-return]


def _version_callback(value: bool) -> None:
    if value:
        console.print(
            Panel(
                f"[bold blue]OpsMind[/] [bold]v{__version__}[/]\nAnsible-Driven Modernization Platform\nLicense: MIT",
                title="Version",
                border_style="blue",
            )
        )
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """OpsMind - Legacy System Modernization Assessment Platform."""
    pass


@app.command()
def discover(
    target: str = typer.Argument(
        ...,
        help="Target hostname, IP, or inventory group (e.g., localhost, 192.168.1.100, web-servers)",
    ),
    method: str = typer.Option(
        "auto",
        "--method",
        "-m",
        help="Discovery method: ansible, native, mock, auto",
    ),
    inventory: str | None = typer.Option(
        None,
        "--inventory",
        "-i",
        help="Path to Ansible inventory file",
    ),
    ssh_user: str | None = typer.Option(
        None,
        "--ssh-user",
        "-u",
        help="SSH username for remote hosts",
    ),
    ssh_key: str | None = typer.Option(
        None,
        "--ssh-key",
        "-k",
        help="SSH private key path",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for discovery results (JSON)",
    ),
) -> None:
    """Discover system information from target hosts."""
    console.print(f"[bold]Discovering[/] target: [green]{target}[/] (method: {method})")

    engine = _get_engine()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Discovering {target}...", total=None)

        try:
            result = engine.discover(
                target=target,
                method=method,
                inventory=inventory,
                ssh_user=ssh_user,
                ssh_key=ssh_key,
                parallel=True,
            )
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Discovery failed:[/] {exc}")
            raise typer.Exit(code=1)

        progress.update(task, completed=True)

    # Display summary
    console.print()
    console.print(
        Panel(
            f"[bold]Discovery Complete[/]\n\n"
            f"[green]✓[/] Successful hosts: {result.successful_hosts}\n"
            f"[red]✗[/] Failed hosts: {result.failed_hosts}\n"
            f"[blue]⏱[/] Duration: {result.total_duration_ms:.0f}ms",
            title="Results",
            border_style="green",
        )
    )

    for hostname, host_data in result.hosts.items():
        hw = host_data.hardware
        sw = host_data.software
        sec = host_data.security

        table = Table(title=f"Host: {hostname}", box=None)
        table.add_column("Category", style="cyan")
        table.add_column("Detail", style="white")

        table.add_row("OS", f"{sw.os_name} {sw.os_version}")
        table.add_row("Kernel", sw.kernel)
        table.add_row("CPU", f"{hw.cpu.model} ({hw.cpu.cores}C/{hw.cpu.threads}T)")
        table.add_row("Memory", f"{hw.memory.total_gb:.1f}GB total / {hw.memory.available_gb:.1f}GB free")
        table.add_row("Disks", f"{len(hw.disks)} mount points")
        table.add_row("Services", f"{len(sw.services)} running")
        table.add_row("Packages", f"{len(sw.packages)} installed")
        table.add_row(
            "Security",
            f"Firewall: {'✓' if sec.firewall_active else '✗'}, Updates: {sec.security_updates_count or 'N/A'}",
        )
        table.add_row("Source", host_data.metadata.source.value)
        table.add_row("Confidence", host_data.metadata.confidence.value)

        if host_data.metadata.warnings:
            table.add_row("Warnings", "[yellow]" + "; ".join(host_data.metadata.warnings) + "[/]")

        console.print(table)
        console.print()

    # Save results if requested
    if output:
        output_path = Path(output)
        save_data = {}
        for hostname, host_data in result.hosts.items():
            save_data[hostname] = json.loads(host_data.model_dump_json())
        save_data["_metadata"] = {
            "total_duration_ms": result.total_duration_ms,
            "successful_hosts": result.successful_hosts,
            "failed_hosts": result.failed_hosts,
        }
        output_path.write_text(json.dumps(save_data, indent=2, default=str))
        console.print(f"[green]Results saved to:[/] {output_path}")


@app.command()
def assess(
    report_format: str = typer.Option(
        "markdown",
        "--report-format",
        "-f",
        help="Report format: markdown, json, html",
    ),
    detail_level: str = typer.Option(
        "detailed",
        "--detail-level",
        "-d",
        help="Detail level: executive, summary, detailed, raw",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for the report",
    ),
) -> None:
    """Assess discovery results and generate report."""
    # Check if we have discovery results from a previous command
    if "last_discovery" not in _state:
        err_console.print("[yellow]No discovery results found. Running discovery on localhost first...[/]")
        engine = _get_engine()
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as p:
                p.add_task("Discovering localhost...")
                _state["last_discovery"] = engine.discover("localhost", method="mock")
        except Exception as exc:
            err_console.print(f"[bold red]Discovery failed:[/] {exc}")
            raise typer.Exit(code=1)

    console.print("[bold]Assessing containerization feasibility...[/]")
    engine = _get_engine()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating systems...", total=None)

        try:
            assessment_results = engine.assess(_state["last_discovery"], detail_level=detail_level)
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Assessment failed:[/] {exc}")
            raise typer.Exit(code=1)

        progress.update(task, completed=True)

    console.print()
    for hostname, result in assessment_results.items():
        feas = result.feasibility
        color = "green" if feas.overall_score >= 70 else "yellow" if feas.overall_score >= 40 else "red"
        console.print(
            Panel(
                f"[bold]{hostname}[/]\n\n"
                f"Feasibility Score: [bold {color}]{feas.overall_score:.1f}/100[/]\n"
                f"Complexity: [bold]{feas.complexity.value.upper()}[/]\n"
                f"Risk Level: [bold]{feas.risk_level.value.upper()}[/]\n"
                f"Strategy: {result.migration_strategy.strategy_type}\n"
                f"Estimated Effort: {result.complexity.estimated_effort_days} days\n\n"
                f"{feas.summary}",
                title="Assessment Result",
                border_style=color,
            )
        )

    # Generate report
    console.print(f"\n[bold]Generating {report_format} report...[/]")

    if not output:
        output = f"opsmind_report.{report_format}"

    try:
        report_data = engine.generate_report(
            assessment_results,
            format=report_format,
            detail_level=detail_level,
            output_dir=str(Path(output).parent) if Path(output).parent else None,
        )
    except Exception as exc:
        err_console.print(f"[bold red]Report generation failed:[/] {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]Report generated:[/] {output}")
    _state["last_assessment"] = assessment_results
    _state["last_report_data"] = report_data


@app.command()
def generate(
    artifact: str = typer.Argument(..., help="Artifact to generate: docker, migration-plan"),
    optimize: str | None = typer.Option(
        None,
        "--optimize",
        "-o",
        help="Optimization target: performance, size, cost",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        "-d",
        help="Output directory for generated artifacts",
    ),
) -> None:
    """Generate remediation artifacts (Docker, migration plans)."""
    if "last_assessment" not in _state:
        err_console.print("[yellow]No assessment results. Running full pipeline first...[/]")
        engine = _get_engine()
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            p.add_task("Running discovery...")
            _state["last_discovery"] = engine.discover("localhost", method="mock")
        _state["last_assessment"] = engine.assess(_state["last_discovery"])

    engine = _get_engine()
    output_dir = output_dir or os.getcwd()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Generating {artifact}...", total=None)

        try:
            if artifact == "docker":
                artifacts = engine.generate_remediation(
                    _state["last_assessment"], output_dir=output_dir, optimize=optimize
                )
                files = artifacts.get("docker", [])
            elif artifact in ("migration-plan", "migration_plan"):
                from opsmind.remediation.generators.migration_plan import MigrationPlanGenerator

                gen = MigrationPlanGenerator(output_dir=output_dir)
                files = gen.generate(_state["last_assessment"])
            else:
                progress.stop()
                err_console.print(f"[red]Unknown artifact: {artifact}[/]")
                err_console.print("Supported: docker, migration-plan")
                raise typer.Exit(code=1)
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Generation failed:[/] {exc}")
            raise typer.Exit(code=1)

        progress.update(task, completed=True)

    console.print(f"\n[green]Generated {len(files)} file(s):[/]")
    for f in files:
        console.print(f"  [blue]✓[/] {f}")


@app.command()
def report(
    action: str = typer.Argument("show", help="Action: show, export, compare"),
    format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Report format: markdown, json, html",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path",
    ),
    baseline: str | None = typer.Option(
        None,
        "--baseline",
        "-b",
        help="Baseline report path for comparison",
    ),
) -> None:
    """View, export, or compare assessment reports."""
    if action == "show":
        if "last_report_data" not in _state:
            err_console.print("[yellow]No report data. Run 'opsmind assess' first.[/]")
            raise typer.Exit(code=1)
        report_data = _state["last_report_data"]

        console.print(
            Panel(
                f"[bold]{report_data.metadata.title}[/]\n\n"
                f"Generated: {report_data.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Hosts: {report_data.metadata.total_hosts}\n"
                f"Confidence: {report_data.metadata.confidence}",
                title="Report Summary",
                border_style="blue",
            )
        )
        console.print(f"\n{report_data.executive_summary}")

        if report_data.sections:
            for section in report_data.sections[:3]:
                console.print(f"\n[bold cyan]## {section.title}[/]")
                content_preview = section.content[:500]
                console.print(content_preview)

    elif action == "export":
        if "last_assessment" not in _state:
            err_console.print("[yellow]No data to export. Run 'opsmind assess' first.[/]")
            raise typer.Exit(code=1)

        engine = _get_engine()
        output = output or f"opsmind_report.{format}"

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            p.add_task(f"Exporting {format} report...")
            engine.generate_report(
                _state["last_assessment"],
                format=format,
                output_dir=str(Path(output).parent) if Path(output).parent else None,
            )

        console.print(f"[green]Report exported to:[/] {output}")

    elif action == "compare":
        if not baseline:
            err_console.print("[red]--baseline is required for compare action[/]")
            raise typer.Exit(code=1)

        if not os.path.exists(baseline):
            err_console.print(f"[red]Baseline file not found: {baseline}[/]")
            raise typer.Exit(code=1)

        if "last_report_data" not in _state:
            err_console.print("[yellow]No current report to compare. Run assessment first.[/]")
            raise typer.Exit(code=1)

        try:
            with open(baseline) as f:
                baseline_data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            err_console.print(f"[red]Failed to read baseline: {exc}[/]")
            raise typer.Exit(code=1)

        current = _state["last_report_data"]
        current_score = current.assessment_summary.get("average_score", 0)
        baseline_score = baseline_data.get("assessment_summary", {}).get("average_score", 0)
        delta = current_score - baseline_score

        console.print(
            Panel(
                f"[bold]Report Comparison[/]\n\n"
                f"Baseline Score: {baseline_score:.1f}\n"
                f"Current Score:  {current_score:.1f}\n"
                f"Delta:          [{'green' if delta >= 0 else 'red'}]{delta:+.1f}[/]",
                title="Comparison",
                border_style="blue",
            )
        )

    else:
        err_console.print(f"[red]Unknown action: {action}. Use: show, export, compare[/]")
        raise typer.Exit(code=1)


@app.command()
def validate(
    check: bool = typer.Option(
        False,
        "--check",
        "-c",
        help="Check configuration validity",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        "-x",
        help="Attempt to fix configuration issues",
    ),
) -> None:
    """Validate system configuration and dependencies."""
    from opsmind.utils.validation import validate_config

    issues: list[str] = []
    warnings: list[str] = []

    console.print("[bold]OpsMind System Validation[/]\n")

    # Check Python version
    py_ver = sys.version_info
    if py_ver >= (3, 11):
        console.print(f"[green]✓[/] Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    else:
        issues.append(f"Python {py_ver.major}.{py_ver.minor} - 3.11+ required")

    # Check Ansible
    from opsmind.utils.ansible_utils import check_ansible_available, get_ansible_version

    if check_ansible_available():
        ver = get_ansible_version()
        console.print(f"[green]✓[/] Ansible: {ver or 'installed'}")
    else:
        warnings.append("Ansible not found - using mock/native fallback")
        console.print("[yellow]○[/] Ansible: not installed (fallback available)")

    # Check Docker
    try:
        import subprocess

        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            console.print(f"[green]✓[/] Docker: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warnings.append("Docker not installed - remediation generation unavailable")
        console.print("[yellow]○[/] Docker: not installed")

    # Check psutil
    try:
        import psutil  # noqa: F401

        console.print("[green]✓[/] psutil: installed")
    except ImportError:
        warnings.append("psutil not installed - native discovery limited")
        console.print("[yellow]○[/] psutil: not installed")

    # Check configuration
    config_issues = validate_config({})
    for issue in config_issues:
        issues.append(issue)

    console.print()
    if issues:
        console.print("[red]Issues found:[/]")
        for issue in issues:
            console.print(f"  [red]✗[/] {issue}")

    if warnings:
        console.print("[yellow]Warnings:[/]")
        for w in warnings:
            console.print(f"  [yellow]○[/] {w}")

    if not issues and not warnings:
        console.print("[green]All checks passed![/]")
    elif not issues:
        console.print("\n[yellow]All systems operational (with warnings).[/]")


@app.command()
def pipeline(
    target: str = typer.Argument("localhost", help="Target hostname, IP, or group"),
    method: str = typer.Option(
        "auto",
        "--method",
        "-m",
        help="Discovery method",
    ),
    report_format: str = typer.Option(
        "markdown",
        "--report-format",
        "-f",
        help="Report format",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
    ),
    generate_remediation: bool = typer.Option(
        False,
        "--remediation",
        "-r",
        help="Generate remediation artifacts",
    ),
    optimize: str | None = typer.Option(
        None,
        "--optimize",
        help="Optimization target for remediation",
    ),
) -> None:
    """Run the complete discovery -> assessment -> reporting pipeline."""
    output_dir = output_dir or os.getcwd()

    console.print(
        Panel(
            "[bold blue]OpsMind Pipeline[/]\n\n"
            f"Target: [green]{target}[/]\n"
            f"Method: {method}\n"
            f"Report: {report_format}\n"
            f"Output: {output_dir}",
            title="Configuration",
            border_style="blue",
        )
    )

    engine = _get_engine()

    overall_start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        # Discovery phase
        disc_task = progress.add_task("[cyan]Phase 1/3: Discovering...", total=None)
        try:
            disc_result = engine.discover(target, method=method)
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Pipeline failed at discovery:[/] {exc}")
            raise typer.Exit(code=1)
        progress.update(disc_task, completed=True)

        # Assessment phase
        asm_task = progress.add_task("[cyan]Phase 2/3: Assessing...", total=None)
        try:
            asm_results = engine.assess(disc_result, detail_level="detailed")
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Pipeline failed at assessment:[/] {exc}")
            raise typer.Exit(code=1)
        progress.update(asm_task, completed=True)

        # Report phase
        rep_task = progress.add_task(f"[cyan]Phase 3/3: Generating {report_format} report...", total=None)
        try:
            engine.generate_report(
                asm_results,
                format=report_format,
                output_dir=output_dir,
            )
        except Exception as exc:
            progress.stop()
            err_console.print(f"[bold red]Pipeline failed at reporting:[/] {exc}")
            raise typer.Exit(code=1)
        progress.update(rep_task, completed=True)

    total_time = time.time() - overall_start

    console.print()
    console.print(
        Panel(
            f"[bold green]Pipeline Complete![/]\n\n"
            f"Discovery: [green]{disc_result.successful_hosts}[/] hosts successful\n"
            f"Assessment: [green]{len(asm_results)}[/] hosts evaluated\n"
            f"Report: {output_dir}/opsmind_report.{report_format}\n"
            f"Total Time: [bold]{total_time:.1f}s[/]",
            title="Summary",
            border_style="green",
        )
    )

    # Show scores
    table = Table(title="Host Assessment Scores")
    table.add_column("Host", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Complexity")
    table.add_column("Risk")
    table.add_column("Strategy")

    for hostname, result in asm_results.items():
        score = result.feasibility.overall_score
        color = "green" if score >= 70 else "yellow" if score >= 40 else "red"
        table.add_row(
            hostname,
            f"[{color}]{score:.1f}[/]",
            result.feasibility.complexity.value,
            result.feasibility.risk_level.value,
            result.migration_strategy.strategy_type,
        )
    console.print(table)

    _state["last_discovery"] = disc_result
    _state["last_assessment"] = asm_results


@app.command()
def demo() -> None:
    """Run an interactive demo showcasing OpsMind capabilities."""
    console.print(
        Panel.fit(
            "[bold blue]OpsMind Interactive Demo[/]\n\n"
            "This demo will showcase OpsMind's key capabilities:\n"
            "1. [cyan]System Discovery[/] - Mock legacy system detection\n"
            "2. [cyan]Intelligent Assessment[/] - Multi-dimension scoring\n"
            "3. [cyan]Report Generation[/] - Professional reports\n"
            "4. [cyan]Docker Artifacts[/] - Automated containerization",
            border_style="blue",
        )
    )

    from opsmind.core.engine import OpsMindEngine

    engine = OpsMindEngine()

    # Phase 1: Discover mock legacy systems
    console.print("\n[bold cyan]Phase 1: System Discovery[/]")
    console.print("Discovering legacy systems...\n")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        p.add_task("[green]Scanning legacy infrastructure...")
        time.sleep(0.5)

    disc_result = engine.discover("legacy-centos", method="mock")
    disc_result.hosts["legacy-app-01"] = disc_result.hosts.pop(list(disc_result.hosts.keys())[0])

    console.print(f"[green]✓[/] Discovered {disc_result.total_hosts} system(s)\n")

    hw = list(disc_result.hosts.values())[0].hardware
    sw = list(disc_result.hosts.values())[0].software
    table = Table(title="Discovered System: legacy-app-01")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("OS", f"{sw.os_name} {sw.os_version}")
    table.add_row("Kernel", sw.kernel)
    table.add_row("CPU", f"{hw.cpu.model}")
    table.add_row("Cores", f"{hw.cpu.cores}C / {hw.cpu.threads}T")
    table.add_row("Memory", f"{hw.memory.total_gb}GB total, {hw.memory.available_gb}GB available")
    table.add_row(
        "Disks",
        f"{len(hw.disks)} mount points "
        f"({(sum(d.used_gb for d in hw.disks) / sum(d.total_gb for d in hw.disks)) * 100:.0f}% utilized)",
    )
    table.add_row("Data Source", "Mock (Demo Mode)")
    console.print(table)

    # Phase 2: Assessment
    console.print("\n[bold cyan]Phase 2: Intelligent Assessment[/]")
    console.print("Evaluating containerization feasibility...\n")

    asm_results = engine.assess(disc_result)

    result = list(asm_results.values())[0]
    feas = result.feasibility

    color = "green" if feas.overall_score >= 70 else "yellow" if feas.overall_score >= 40 else "red"
    console.print(
        Panel(
            f"Overall Score: [bold {color}]{feas.overall_score:.1f}/100[/]\n"
            f"Complexity: [bold]{feas.complexity.value.upper()}[/]\n"
            f"Risk Level: [bold]{feas.risk_level.value.upper()}[/]\n"
            f"Strategy: [bold]{result.migration_strategy.strategy_type}[/]\n"
            f"Estimated Effort: {result.complexity.estimated_effort_days} days",
            title="Assessment Result",
            border_style=color,
        )
    )

    dim_table = Table(title="Dimension Scores")
    dim_table.add_column("Dimension", style="cyan")
    dim_table.add_column("Score", justify="right")
    dim_table.add_column("Weight")
    dim_table.add_column("Status")
    for ds in feas.dimension_scores:
        status = "[green]✓[/]" if ds.score >= 70 else "[yellow]△[/]" if ds.score >= 40 else "[red]✗[/]"
        dim_table.add_row(
            ds.dimension.value.replace("_", " ").title(),
            f"{ds.score:.1f}",
            f"{ds.weight:.0%}",
            status,
        )
    console.print(dim_table)

    # Phase 3: Report
    console.print("\n[bold cyan]Phase 3: Report Generation[/]")
    output_path = "opsmind_demo_report.md"
    engine.generate_report(asm_results, format="markdown", output_dir=".")
    console.print(f"[green]✓[/] Markdown report: {output_path}")

    output_path_json = "opsmind_demo_report.json"
    engine.generate_report(asm_results, format="json", output_dir=".")
    console.print(f"[green]✓[/] JSON report: {output_path_json}")

    output_path_html = "opsmind_demo_report.html"
    engine.generate_report(asm_results, format="html", output_dir=".")
    console.print(f"[green]✓[/] HTML report: {output_path_html}")

    # Phase 4: Remediation
    console.print("\n[bold cyan]Phase 4: Remediation Artifacts[/]")
    from opsmind.remediation.generators.docker import DockerGenerator
    from opsmind.remediation.generators.migration_plan import MigrationPlanGenerator

    dg = DockerGenerator(output_dir="opsmind_artifacts")
    docker_files = dg.generate(asm_results)
    for f in docker_files:
        console.print(f"[green]✓[/] Generated: {f}")

    mp = MigrationPlanGenerator(output_dir="opsmind_artifacts")
    plan_files = mp.generate(asm_results)
    for f in plan_files:
        console.print(f"[green]✓[/] Generated: {f}")

    # Final summary
    console.print("\n[bold green]Demo Complete![/]")
    console.print(
        Panel(
            "[bold]Generated Artifacts:[/]\n\n"
            "[blue]•[/] opsmind_demo_report.md\n"
            "[blue]•[/] opsmind_demo_report.json\n"
            "[blue]•[/] opsmind_demo_report.html\n"
            "[blue]•[/] opsmind_artifacts/docker/legacy-app-01/Dockerfile\n"
            "[blue]•[/] opsmind_artifacts/docker/legacy-app-01/docker-compose.yml\n"
            "[blue]•[/] opsmind_artifacts/plans/legacy-app-01_migration_plan.md\n\n"
            "Run [bold]opsmind discover localhost[/] for real system discovery!\n"
            "Run [bold]opsmind pipeline <target>[/] for the full workflow!",
            title="Summary",
            border_style="green",
        )
    )


@app.command()
def web(
    host: str = typer.Option(
        "0.0.0.0",  # nosec B104
        "--host",
        "-h",
        help="Bind host",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Bind port",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload (development only)",
    ),
) -> None:
    """Start the OpsMind web API server (K8s deployment entrypoint)."""
    try:
        import uvicorn
    except ImportError:
        err_console.print(
            "[bold red]Missing web dependencies.[/]\n\n"
            "The web server requires additional packages. Install them with:\n\n"
            "  [bold]pip install opsmind-tools[web][/]\n"
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold blue]OpsMind Web Server[/]\n\n"
            f"Listening on: [green]http://{host}:{port}[/]\n"
            f"Health check: [green]http://{host}:{port}/health[/]\n"
            f"API docs:     [green]http://{host}:{port}/docs[/]",
            title="Web Server",
            border_style="blue",
        )
    )

    uvicorn.run(
        "opsmind.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    app()
