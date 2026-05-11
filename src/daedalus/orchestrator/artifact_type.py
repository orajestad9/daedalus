from enum import StrEnum


class ArtifactType(StrEnum):
    """Shared platform artifact type identifiers."""

    NORMALIZED_REVIEWS = "normalized_reviews"
    REVIEW_METADATA = "review_metadata"
    WORKFLOW_SUMMARY = "workflow_summary"
    WORKFLOW_RUN_RECORD = "workflow_run_record"
    REVIEW_THEME_SUMMARY = "review_theme_summary"
    EVALUATION_REPORT = "evaluation_report"
    EVALUATION_COMPARISON_REPORT = "evaluation_comparison_report"
    REVIEW_INSIGHTS = "review_insights"
    APPROVAL_RECORD = "approval_record"
    AGENT_OUTPUT = "agent_output"
    VALIDATION_REPORT = "validation_report"
