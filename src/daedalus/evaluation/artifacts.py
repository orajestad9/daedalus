"""Artifact writers for generic evaluation reports."""

from pathlib import Path

from daedalus.evaluation.models import EvaluationReport


def write_evaluation_report_json(
    *,
    report: EvaluationReport,
    output_path: Path,
) -> Path:
    """Write a machine-readable JSON artifact for an evaluation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def write_evaluation_report_markdown(
    *,
    report: EvaluationReport,
    output_path: Path,
) -> Path:
    """Write an inspectable markdown artifact for an evaluation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_evaluation_report_markdown(report), encoding="utf-8")
    return output_path


def _evaluation_report_markdown(report: EvaluationReport) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"- Report ID: `{report.report_id}`",
    ]

    if report.run_id is not None:
        lines.append(f"- Run ID: `{report.run_id}`")
    if report.artifact_path is not None:
        lines.append(f"- Artifact path: `{report.artifact_path}`")

    lines.extend(
        [
            f"- Target name: `{report.target_name}`",
            f"- Target type: `{report.target_type}`",
            f"- Evaluator name: `{report.evaluator_name}`",
            f"- Evaluator version: `{report.evaluator_version}`",
            f"- Created at UTC: `{report.created_at_utc.isoformat()}`",
            f"- Passed: `{report.passed}`",
            f"- Failed count: `{report.failed_count}`",
            f"- Warning count: `{report.warning_count}`",
            f"- Error count: `{report.error_count}`",
            "",
            "## Checks",
            "",
        ]
    )

    if not report.checks:
        lines.append("No evaluation checks were recorded.")
    else:
        for check in report.checks:
            lines.extend(
                [
                    f"### {check.check_name}",
                    "",
                    f"- Status: `{check.status.value}`",
                    f"- Severity: `{check.severity.value}`",
                    f"- Message: {check.message}",
                ]
            )
            if check.details:
                lines.extend(["", "Details:", ""])
                for key, value in check.details.items():
                    lines.append(f"- `{key}`: `{value}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
