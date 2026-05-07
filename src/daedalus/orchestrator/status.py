from enum import StrEnum


class WorkflowStatus(StrEnum):
    """Shared platform workflow execution statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED_APPROVAL_REQUIRED = "blocked_approval_required"
