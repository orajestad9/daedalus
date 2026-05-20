"""Review insight extraction agent using the shared ModelClient boundary."""

import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionInput,
    ReviewInsightExtractionResult,
)
from daedalus.domains.readysetrentables_reviews.review_insight_output_parser import (
    parse_review_insight_extraction_result,
)
from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.types import ModelProvider, ModelRequest


class ReviewInsightExtractionAgent:
    """Extract structured review insights through an injected ModelClient."""

    def __init__(
        self,
        *,
        model_client: ModelClient,
        model_name: str,
        prompt_name: str = DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version: str = DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ) -> None:
        self._model_client = model_client
        self._model_name = model_name
        self._prompt_name = prompt_name
        self._prompt_version = prompt_version

    def run(
        self,
        *,
        input_data: ReviewInsightExtractionInput,
    ) -> ReviewInsightExtractionResult:
        """Return parsed review insight extraction output from the model client."""
        request = ModelRequest(
            run_id=input_data.run_id,
            agent_name="review_insight_extraction_agent",
            provider=ModelProvider.OLLAMA,
            model_name=self._model_name,
            prompt_name=self._prompt_name,
            prompt_version=self._prompt_version,
            input_text=_build_review_insight_prompt(input_data),
            input_artifact_path=_prompt_artifact_path(self._prompt_name, self._prompt_version),
            output_artifact_path=Path("artifacts/readysetrentables/review_insights.json"),
            response_schema_name="ReviewInsightExtractionResult",
            metadata=_metadata_from_input(input_data),
        )
        response = self._model_client.complete(request)

        return parse_review_insight_extraction_result(
            output_text=response.output_text or "",
            run_id=input_data.run_id,
            provider=response.provider,
            model_name=self._model_name,
            prompt_name=self._prompt_name,
            prompt_version=self._prompt_version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
        )


def _build_review_insight_prompt(input_data: ReviewInsightExtractionInput) -> str:
    payload = {
        "market_name": input_data.market_name,
        "neighborhood_name": input_data.neighborhood_name,
        "property_type": input_data.property_type,
        "review_count": input_data.review_count,
        "average_rating": input_data.average_rating,
        "rating_categories": input_data.rating_categories,
        "representative_reviews": input_data.representative_reviews,
    }

    output_schema = {
        "themes": [
            {
                "name": "string",
                "sentiment": "positive|negative|mixed|neutral",
                "evidence_count": 0,
                "summary": "string",
            }
        ],
        "strengths": ["string"],
        "risks": ["string"],
        "guest_expectations": ["string"],
        "raw_insight_summary": "string",
    }

    return "\n\n".join(
        [
            "Extract structured ReadySetRentables review insights from the compact input.",
            "Return only one JSON object.",
            "Do not include Markdown.",
            "Do not include code fences.",
            "Do not include commentary before or after the JSON object.",
            "Do not include trailing commas.",
            "Use this exact schema:",
            json.dumps(output_schema, sort_keys=True, indent=2),
            "Schema rules:",
            "\n".join(
                [
                    "- themes must be an array.",
                    "- evidence_count must be a non-negative integer.",
                    "- all strings must be non-empty.",
                    "- if there are no risks, use an empty array.",
                    "- do not invent facts beyond the provided reviews and ratings.",
                ]
            ),
            "Compact review insight input:",
            json.dumps(payload, sort_keys=True, indent=2),
        ]
    )


def _prompt_artifact_path(prompt_name: str, prompt_version: str) -> Path:
    if prompt_name == DEFAULT_REVIEW_INSIGHT_PROMPT_NAME:
        return Path("prompts/readysetrentables/review_insight_extraction").joinpath(
            f"{prompt_version}.md"
        )
    return Path("prompts").joinpath(*prompt_name.split("/"), f"{prompt_version}.md")


def _metadata_from_input(input_data: ReviewInsightExtractionInput) -> dict[str, str]:
    metadata = {"review_count": str(input_data.review_count)}
    if input_data.market_name is not None:
        metadata["market_name"] = input_data.market_name
    if input_data.neighborhood_name is not None:
        metadata["neighborhood_name"] = input_data.neighborhood_name
    if input_data.property_type is not None:
        metadata["property_type"] = input_data.property_type
    if input_data.average_rating is not None:
        metadata["average_rating"] = str(input_data.average_rating)
    return metadata
