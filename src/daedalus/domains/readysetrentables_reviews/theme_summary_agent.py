"""Review theme summary agent using the shared ModelClient boundary."""

import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    ReviewThemeSummaryInput,
    ReviewThemeSummaryResult,
)
from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.prompts import load_prompt_template
from daedalus.model_clients.types import ModelProvider, ModelRequest


class ReviewThemeSummaryAgent:
    """Summarize compact review theme input through a supplied ModelClient."""

    def __init__(
        self,
        *,
        model_client: ModelClient,
        prompts_root: Path = Path("prompts"),
        model_provider: ModelProvider = ModelProvider.FAKE,
        model_name: str = "fake-model",
    ) -> None:
        self._model_client = model_client
        self._prompts_root = prompts_root
        self._model_provider = model_provider
        self._model_name = model_name

    def summarize(self, input_data: ReviewThemeSummaryInput) -> ReviewThemeSummaryResult:
        """Return a theme summary result from compact review summary input."""
        prompt = load_prompt_template(
            prompt_name=input_data.prompt_name,
            prompt_version=input_data.prompt_version,
            prompts_root=self._prompts_root,
        )
        request = ModelRequest(
            run_id=input_data.run_id,
            agent_name="review_theme_summary_agent",
            provider=self._model_provider,
            model_name=self._model_name,
            prompt_name=input_data.prompt_name,
            prompt_version=input_data.prompt_version,
            input_text=build_review_theme_summary_model_input_text(
                input_data=input_data,
                prompt_text=prompt.text,
            ),
            input_artifact_path=prompt.prompt_path,
            output_artifact_path=Path("artifacts/readysetrentables/review_theme_summary.md"),
            budget=input_data.budget,
            metadata=_metadata_from_input(input_data),
        )
        response = self._model_client.complete(request)

        return ReviewThemeSummaryResult(
            run_id=input_data.run_id,
            summary_text=response.output_text or "",
            themes=[],
            prompt_name=input_data.prompt_name,
            prompt_version=input_data.prompt_version,
            model_provider=response.provider,
            model_name=response.model_name,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
        )


def build_review_theme_summary_model_input_text(
    *,
    input_data: ReviewThemeSummaryInput,
    prompt_text: str,
) -> str:
    """Build safe compact input text for the review theme summary model call."""
    compact_payload = {
        "review_count": input_data.review_count,
        "average_rating": input_data.average_rating,
        "rating_distribution": input_data.rating_distribution,
        "representative_reviews": input_data.representative_reviews,
    }
    return "\n\n".join(
        [
            "Prompt template:",
            prompt_text.strip(),
            "Compact review summary input:",
            json.dumps(compact_payload, sort_keys=True, indent=2),
        ]
    )


def _metadata_from_input(input_data: ReviewThemeSummaryInput) -> dict[str, str]:
    metadata = {"review_count": str(input_data.review_count)}
    if input_data.average_rating is not None:
        metadata["average_rating"] = str(input_data.average_rating)

    return metadata
