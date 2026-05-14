"""Read-only repository boundary for future RSR source extraction."""

import re
from typing import Any

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
)


_ALLOWED_QUERY_PREFIXES = ("select", "with")
_FORBIDDEN_QUERY_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "upsert",
    "merge",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "vacuum",
    "analyze",
    "copy",
    "call",
)


class RsrSourceReadOnlyRepository:
    """Boundary for future read-only RSR source DB extraction."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def extract_source_data(
        self,
        *,
        request: RsrSourceExtractionRequest,
    ) -> RsrSourceExtractionResult:
        """Extract RSR source data when real read-only queries are implemented."""
        _ = request
        msg = "Real RSR source DB queries are not implemented yet."
        raise NotImplementedError(msg)


def ensure_read_only_query(query: str) -> None:
    """Guardrail for future repository SQL; this is not a full SQL parser."""
    stripped_query = query.strip()
    if not stripped_query:
        msg = "RSR source query must not be empty."
        raise ValueError(msg)

    normalized_query = stripped_query.lower()
    if not normalized_query.startswith(_ALLOWED_QUERY_PREFIXES):
        msg = "RSR source query must start with SELECT or WITH."
        raise ValueError(msg)

    for keyword in _FORBIDDEN_QUERY_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized_query):
            msg = "RSR source query contains a non-read-only keyword."
            raise ValueError(msg)
