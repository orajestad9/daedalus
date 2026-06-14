from decimal import Decimal
import inspect
import json
from uuid import uuid4

import pytest

import daedalus.domains.readysetrentables_reviews.review_insight_agent as agent_module
from daedalus.domains.readysetrentables_reviews.review_insight_agent import (
    ReviewInsightExtractionAgent,
    _build_review_insight_prompt,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionInput,
    ReviewInsightExtractionResult,
)
from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


def test_review_insight_extraction_agent_calls_injected_model_client_once() -> None:
    client = CapturingReviewInsightModelClient()
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    agent.run(input_data=_input_data())

    assert client.call_count == 1


def test_review_insight_extraction_agent_passes_prompt_text_to_model_client() -> None:
    client = CapturingReviewInsightModelClient()
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    agent.run(input_data=_input_data())

    assert client.request is not None
    assert client.request.input_text
    assert "Compact review insight input" in client.request.input_text


def test_review_insight_prompt_includes_market_name() -> None:
    prompt = _build_review_insight_prompt(_input_data(market_name="Synthetic Market"))

    assert "Synthetic Market" in prompt


def test_review_insight_prompt_includes_neighborhood_name_when_present() -> None:
    prompt = _build_review_insight_prompt(_input_data(neighborhood_name="Synthetic Neighborhood"))

    assert "Synthetic Neighborhood" in prompt


def test_review_insight_prompt_includes_property_type_when_present() -> None:
    prompt = _build_review_insight_prompt(_input_data(property_type="Synthetic Loft"))

    assert "Synthetic Loft" in prompt


def test_review_insight_prompt_includes_review_count() -> None:
    prompt = _build_review_insight_prompt(_input_data(review_count=12))

    assert '"review_count": 12' in prompt


def test_review_insight_prompt_includes_rating_category_names() -> None:
    prompt = _build_review_insight_prompt(
        _input_data(rating_categories={"synthetic_cleanliness": 4.8})
    )

    assert "synthetic_cleanliness" in prompt


def test_review_insight_prompt_includes_representative_synthetic_reviews() -> None:
    prompt = _build_review_insight_prompt(
        _input_data(representative_reviews=["Synthetic review: easy arrival."])
    )

    assert "Synthetic review: easy arrival." in prompt


def test_review_insight_prompt_asks_for_json_output() -> None:
    prompt = _build_review_insight_prompt(_input_data())

    assert "Return only one JSON object" in prompt
    assert "Do not include Markdown" in prompt
    assert "Do not include code fences" in prompt
    assert "Do not include commentary before or after the JSON object" in prompt
    assert "Do not include trailing commas" in prompt


def test_review_insight_prompt_includes_exact_required_keys() -> None:
    prompt = _build_review_insight_prompt(_input_data())

    assert '"themes"' in prompt
    assert '"name"' in prompt
    assert '"sentiment"' in prompt
    assert '"evidence_count"' in prompt
    assert '"summary"' in prompt
    assert '"strengths"' in prompt
    assert '"risks"' in prompt
    assert '"guest_expectations"' in prompt
    assert '"raw_insight_summary"' in prompt
    assert "positive|negative|mixed|neutral" in prompt


def test_review_insight_prompt_mentions_non_negative_evidence_count() -> None:
    prompt = _build_review_insight_prompt(_input_data())

    assert "evidence_count must be a non-negative integer" in prompt


def test_review_insight_prompt_says_risks_can_be_empty_array() -> None:
    prompt = _build_review_insight_prompt(_input_data())

    assert "if there are no risks, use an empty array" in prompt


def test_review_insight_prompt_says_not_to_invent_facts() -> None:
    prompt = _build_review_insight_prompt(_input_data())

    assert "do not invent facts beyond the provided reviews and ratings" in prompt


def test_review_insight_extraction_agent_parses_valid_model_json() -> None:
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(),
        model_name="synthetic-model",
    )

    result = agent.run(input_data=_input_data())

    assert isinstance(result, ReviewInsightExtractionResult)
    assert result.themes[0].name == "arrival clarity"
    assert result.strengths == ["Clear synthetic arrival details"]
    assert result.raw_insight_summary == "Synthetic guests praise arrival clarity."


def test_review_insight_extraction_agent_result_run_id_comes_from_input() -> None:
    input_data = _input_data()
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(),
        model_name="synthetic-model",
    )

    result = agent.run(input_data=input_data)

    assert result.run_id == input_data.run_id


def test_review_insight_extraction_agent_result_prompt_identity_comes_from_constructor() -> None:
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(),
        model_name="synthetic-model",
        prompt_name="custom-review-insight-prompt",
        prompt_version="v7",
    )

    result = agent.run(input_data=_input_data())

    assert result.prompt_name == "custom-review-insight-prompt"
    assert result.prompt_version == "v7"


def test_review_insight_extraction_agent_result_model_name_comes_from_constructor() -> None:
    client = CapturingReviewInsightModelClient(response_model_name="response-model")
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="constructor-model")

    result = agent.run(input_data=_input_data())

    assert result.model_name == "constructor-model"


def test_review_insight_extraction_agent_result_provider_comes_from_response() -> None:
    client = CapturingReviewInsightModelClient(response_provider=ModelProvider.FAKE)
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    result = agent.run(input_data=_input_data())

    assert result.provider == ModelProvider.FAKE


def test_review_insight_extraction_agent_token_metadata_is_preserved() -> None:
    client = CapturingReviewInsightModelClient(input_tokens=14, output_tokens=9, total_tokens=23)
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    result = agent.run(input_data=_input_data())

    assert result.input_tokens == 14
    assert result.output_tokens == 9
    assert result.total_tokens == 23


def test_review_insight_extraction_agent_cost_metadata_is_preserved() -> None:
    client = CapturingReviewInsightModelClient(estimated_cost_usd=Decimal("0.003"))
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    result = agent.run(input_data=_input_data())

    assert result.estimated_cost_usd == Decimal("0.003")


def test_review_insight_extraction_agent_builds_model_request_metadata() -> None:
    client = CapturingReviewInsightModelClient()
    agent = ReviewInsightExtractionAgent(model_client=client, model_name="synthetic-model")

    agent.run(input_data=_input_data())

    assert client.request is not None
    assert client.request.agent_name == "review_insight_extraction_agent"
    assert client.request.provider == ModelProvider.OLLAMA
    assert client.request.model_name == "synthetic-model"
    assert client.request.prompt_name == "readysetrentables_review_insight_extraction"
    assert client.request.prompt_version == "v0"
    assert client.request.response_schema_name == "ReviewInsightExtractionResult"


def test_review_insight_extraction_agent_error_does_not_expose_raw_model_output() -> None:
    raw_output = (
        '{"themes":[{"name":"arrival clarity","sentiment":"positive"}],'
        '"raw_insight_summary":"Synthetic private model output"}'
    )
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(output_text=raw_output),
        model_name="synthetic-model",
    )

    with pytest.raises(ValueError) as exc_info:
        agent.run(input_data=_input_data())

    error_message = str(exc_info.value)
    assert raw_output not in error_message
    assert "Synthetic private model output" not in error_message


def test_review_insight_extraction_agent_preserves_safe_parser_message() -> None:
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(output_text="not json at all"),
        model_name="synthetic-model",
    )

    with pytest.raises(ValueError) as exc_info:
        agent.run(input_data=_input_data())

    assert str(exc_info.value) == "Model output did not contain a valid JSON object."


def test_review_insight_extraction_agent_error_does_not_expose_review_text() -> None:
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(output_text="not json at all"),
        model_name="synthetic-model",
    )

    with pytest.raises(ValueError) as exc_info:
        agent.run(
            input_data=_input_data(
                representative_reviews=["SYNTHETIC_REVIEW_TEXT_DO_NOT_LEAK"],
            )
        )

    assert "SYNTHETIC_REVIEW_TEXT_DO_NOT_LEAK" not in str(exc_info.value)


def test_review_insight_extraction_agent_does_not_print_prompt_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = ReviewInsightExtractionAgent(
        model_client=CapturingReviewInsightModelClient(),
        model_name="synthetic-model",
    )

    agent.run(input_data=_input_data())

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert "Compact review insight input" not in combined_output
    assert "Return only one JSON object" not in combined_output


def test_review_insight_extraction_agent_does_not_instantiate_ollama_client() -> None:
    source = inspect.getsource(agent_module)

    assert "OllamaModelClient" not in source


def test_review_insight_extraction_agent_does_not_call_real_providers() -> None:
    source = inspect.getsource(agent_module)

    assert "urllib" not in source
    assert "requests" not in source
    assert ".complete(" in source


def test_review_insight_extraction_agent_does_not_connect_to_db() -> None:
    source = inspect.getsource(agent_module)

    assert "psycopg" not in source
    assert "postgres" not in source.lower()
    assert "connect(" not in source


class CapturingReviewInsightModelClient:
    def __init__(
        self,
        *,
        output_text: str | None = None,
        response_provider: ModelProvider = ModelProvider.FAKE,
        response_model_name: str | None = None,
        input_tokens: int | None = 10,
        output_tokens: int | None = 8,
        total_tokens: int | None = 18,
        estimated_cost_usd: Decimal | None = Decimal("0"),
    ) -> None:
        self.output_text = output_text or json.dumps(_model_output_payload())
        self.response_provider = response_provider
        self.response_model_name = response_model_name
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.request: ModelRequest | None = None
        self.call_count = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.call_count += 1
        self.request = request
        return ModelResponse(
            invocation_id=uuid4(),
            status=ModelInvocationStatus.COMPLETED,
            provider=self.response_provider,
            model_name=self.response_model_name or request.model_name,
            output_text=self.output_text,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            estimated_cost_usd=self.estimated_cost_usd,
        )


def _input_data(
    *,
    market_name: str | None = "Synthetic Market",
    neighborhood_name: str | None = "Synthetic Neighborhood",
    property_type: str | None = "Synthetic Apartment",
    review_count: int = 2,
    average_rating: float | None = 4.7,
    rating_categories: dict[str, float] | None = None,
    representative_reviews: list[str] | None = None,
) -> ReviewInsightExtractionInput:
    return ReviewInsightExtractionInput(
        run_id=uuid4(),
        review_count=review_count,
        market_name=market_name,
        neighborhood_name=neighborhood_name,
        property_type=property_type,
        average_rating=average_rating,
        rating_categories=rating_categories or {"synthetic_location": 4.9},
        representative_reviews=representative_reviews
        or ["Synthetic review: clear arrival details."],
    )


def _model_output_payload() -> dict[str, object]:
    return {
        "themes": [
            {
                "name": "arrival clarity",
                "sentiment": "positive",
                "evidence_count": 2,
                "summary": "Guests value clear synthetic arrival guidance.",
            }
        ],
        "strengths": ["Clear synthetic arrival details"],
        "risks": ["Occasional synthetic street noise"],
        "guest_expectations": ["Send arrival details before check-in"],
        "raw_insight_summary": "Synthetic guests praise arrival clarity.",
    }
