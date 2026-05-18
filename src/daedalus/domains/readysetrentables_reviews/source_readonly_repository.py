"""Read-only repository boundary for future RSR source extraction."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
import re
from typing import Any

from psycopg.rows import dict_row

from daedalus.domains.readysetrentables_reviews.source_db_mappers import (
    build_source_extraction_result_from_rows,
)
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
_LISTING_FALLBACK_LIMIT = 25


class RsrSourceReadOnlyRepository:
    """Read-only repository for sanitized RSR source DB extraction."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self.connection = connection

    def extract_source_data(
        self,
        *,
        request: RsrSourceExtractionRequest,
    ) -> RsrSourceExtractionResult:
        """Extract sanitized RSR source data using only SELECT queries."""
        review_rows = _shape_review_rows(self._fetch_review_rows(request))

        listing_rows: list[Mapping[str, Any]] = []
        if request.include_listing_context:
            listing_ids = _listing_ids_from_review_rows(review_rows)
            listing_rows = _shape_listing_rows(self._fetch_listing_rows(request, listing_ids))

        neighborhood_row: Mapping[str, Any] | None = None
        if request.include_neighborhood_context:
            fetched_neighborhood_rows = self._fetch_neighborhood_rows(request)
            if fetched_neighborhood_rows:
                neighborhood_row = _shape_neighborhood_row(fetched_neighborhood_rows[0])

        try:
            return build_source_extraction_result_from_rows(
                request=request,
                review_rows=review_rows,
                listing_rows=listing_rows,
                neighborhood_row=neighborhood_row,
                source_name="readysetrentables",
                source_version="v0",
                metadata={
                    "extraction_mode": "read_only",
                    "repository": "RsrSourceReadOnlyRepository",
                },
            )
        except Exception:
            msg = "Unable to map RSR source extraction rows."
            raise RuntimeError(msg) from None

    def _fetch_review_rows(self, request: RsrSourceExtractionRequest) -> list[Mapping[str, Any]]:
        conditions = [
            "(r.market = %(market_name)s OR l.market = %(market_name)s)",
            "r.comments IS NOT NULL",
            "btrim(r.comments) <> ''",
        ]
        params: dict[str, object] = {"market_name": request.market_name}

        if request.neighborhood_name is not None:
            conditions.append("l.neighbourhood = %(neighborhood_name)s")
            params["neighborhood_name"] = request.neighborhood_name
        if request.property_type is not None:
            conditions.append("l.property_type = %(property_type)s")
            params["property_type"] = request.property_type

        limit_clause = ""
        if request.max_reviews is not None:
            limit_clause = "LIMIT %(max_reviews)s"
            params["max_reviews"] = request.max_reviews

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT
                r.id::text AS review_id,
                r.listing_id::text AS listing_id,
                NULL::numeric AS rating,
                r.comments AS review_text,
                r.date::timestamp AS created_at,
                r.market AS market,
                r.market_id AS market_id
            FROM public.reviews AS r
            LEFT JOIN public.listings AS l
                ON l.id = r.listing_id
            WHERE {where_clause}
            ORDER BY r.date DESC NULLS LAST, r.id DESC
            {limit_clause}
        """
        return self._fetch_all(query, params)

    def _fetch_listing_rows(
        self,
        request: RsrSourceExtractionRequest,
        listing_ids: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        params: dict[str, object] = {}
        if listing_ids:
            where_clause = "l.id::text = ANY(%(listing_ids)s)"
            params["listing_ids"] = list(listing_ids)
            limit = len(listing_ids)
        else:
            conditions = ["l.market = %(market_name)s"]
            params["market_name"] = request.market_name
            if request.neighborhood_name is not None:
                conditions.append("l.neighbourhood = %(neighborhood_name)s")
                params["neighborhood_name"] = request.neighborhood_name
            if request.property_type is not None:
                conditions.append("l.property_type = %(property_type)s")
                params["property_type"] = request.property_type
            where_clause = " AND ".join(conditions)
            limit = _LISTING_FALLBACK_LIMIT

        params["listing_limit"] = limit
        query = f"""
            SELECT
                l.id::text AS listing_id,
                l.name AS listing_name,
                l.property_type AS property_type,
                l.bedrooms AS bedrooms,
                l.bathrooms AS bathrooms,
                l.accommodates AS accommodates,
                l.review_scores_rating AS average_rating,
                l.room_type AS room_type,
                l.neighbourhood AS neighbourhood,
                l.market AS market,
                l.market_id AS market_id,
                l.review_scores_accuracy AS review_scores_accuracy,
                l.review_scores_cleanliness AS review_scores_cleanliness,
                l.review_scores_checkin AS review_scores_checkin,
                l.review_scores_communication AS review_scores_communication,
                l.review_scores_location AS review_scores_location,
                l.review_scores_value AS review_scores_value
            FROM public.listings AS l
            WHERE {where_clause}
            ORDER BY l.number_of_reviews DESC NULLS LAST, l.id DESC
            LIMIT %(listing_limit)s
        """
        return self._fetch_all(query, params)

    def _fetch_neighborhood_rows(
        self,
        request: RsrSourceExtractionRequest,
    ) -> list[Mapping[str, Any]]:
        conditions = [
            "(n.market = %(market_name)s OR m.name = %(market_name)s "
            "OR m.market_key = %(market_name)s)"
        ]
        params: dict[str, object] = {"market_name": request.market_name}
        if request.neighborhood_name is not None:
            conditions.append("n.name = %(neighborhood_name)s")
            params["neighborhood_name"] = request.neighborhood_name

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT
                COALESCE(m.name, n.market) AS market_name,
                n.name AS neighborhood_name,
                NULL::text AS city,
                NULL::text AS state,
                NULL::text AS country,
                n.market_id AS market_id,
                m.market_key AS market_key,
                n.id AS neighborhood_id
            FROM public.neighborhoods AS n
            LEFT JOIN public.markets AS m
                ON m.id = n.market_id
            WHERE {where_clause}
            ORDER BY n.name ASC, n.id ASC
            LIMIT 1
        """
        return self._fetch_all(query, params)

    def _fetch_all(self, query: str, params: Mapping[str, object]) -> list[Mapping[str, Any]]:
        ensure_read_only_query(query)
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


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


def _shape_review_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        {
            "review_id": _string_or_none(row.get("review_id")),
            "listing_id": _string_or_none(row.get("listing_id")),
            "rating": row.get("rating"),
            "review_text": row.get("review_text"),
            "created_at": _datetime_or_none(row.get("created_at")),
            "metadata": _metadata_from_values(
                {
                    "source_table": "public.reviews",
                    "market": row.get("market"),
                    "market_id": row.get("market_id"),
                }
            ),
        }
        for row in rows
    ]


def _shape_listing_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        {
            "listing_id": _string_or_none(row.get("listing_id")),
            "listing_name": row.get("listing_name"),
            "property_type": row.get("property_type"),
            "bedrooms": row.get("bedrooms"),
            "bathrooms": row.get("bathrooms"),
            "accommodates": row.get("accommodates"),
            "average_rating": row.get("average_rating"),
            "metadata": _metadata_from_values(
                {
                    "room_type": row.get("room_type"),
                    "neighbourhood": row.get("neighbourhood"),
                    "market": row.get("market"),
                    "market_id": row.get("market_id"),
                    "review_scores_accuracy": row.get("review_scores_accuracy"),
                    "review_scores_cleanliness": row.get("review_scores_cleanliness"),
                    "review_scores_checkin": row.get("review_scores_checkin"),
                    "review_scores_communication": row.get("review_scores_communication"),
                    "review_scores_location": row.get("review_scores_location"),
                    "review_scores_value": row.get("review_scores_value"),
                }
            ),
        }
        for row in rows
    ]


def _shape_neighborhood_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "market_name": row.get("market_name"),
        "neighborhood_name": row.get("neighborhood_name"),
        "city": row.get("city"),
        "state": row.get("state"),
        "country": row.get("country"),
        "metadata": _metadata_from_values(
            {
                "market_id": row.get("market_id"),
                "market_key": row.get("market_key"),
                "neighborhood_id": row.get("neighborhood_id"),
            }
        ),
    }


def _listing_ids_from_review_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    listing_ids: list[str] = []
    for row in rows:
        listing_id = _string_or_none(row.get("listing_id"))
        if listing_id is not None and listing_id not in listing_ids:
            listing_ids.append(listing_id)
    return listing_ids


def _metadata_from_values(values: Mapping[str, object]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key, value in values.items():
        metadata_value = _metadata_value(value)
        if metadata_value is not None:
            metadata[key] = metadata_value
    return metadata


def _metadata_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _datetime_or_none(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return value
