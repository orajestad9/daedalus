from enum import StrEnum


class WorkflowName(StrEnum):
    """Shared platform workflow names."""

    READYSETRENTABLES_REVIEW_NORMALIZATION = "readysetrentables_review_normalization"


class WorkflowDomain(StrEnum):
    """Shared platform workflow domains."""

    READYSETRENTABLES_REVIEWS = "readysetrentables_reviews"
