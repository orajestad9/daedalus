from decimal import Decimal
from uuid import uuid4

from daedalus.domains.readysetrentables_reviews.theme_summary_agent import (
    ReviewThemeSummaryAgent,
    build_review_theme_summary_model_input_text,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    DEFAULT_REVIEW_THEME_PROMPT_NAME,
    DEFAULT_REVIEW_THEME_PROMPT_VERSION,
    ReviewThemeSummaryInput,
    ReviewThemeSummaryResult,
)
from daedalus.model_clients.fake import FakeModelClient
from daedalus.model_clients.types import (
    ModelBudget,
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


def test_review_theme_summary_agent_accepts_fake_model_client() -> None:
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())

    result = agent.summarize(_summary_input())

    assert isinstance(result, ReviewThemeSummaryResult)


def test_review_theme_summary_agent_summarize_returns_result() -> None:
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())

    result = agent.summarize(_summary_input())

    assert isinstance(result, ReviewThemeSummaryResult)


def test_review_theme_summary_agent_result_preserves_run_id() -> None:
    input_data = _summary_input()
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())

    result = agent.summarize(input_data)

    assert result.run_id == input_data.run_id


def test_review_theme_summary_agent_summary_text_comes_from_fake_model_output() -> None:
    agent = ReviewThemeSummaryAgent(
        model_client=FakeModelClient(output_text="deterministic theme summary")
    )

    result = agent.summarize(_summary_input())

    assert result.summary_text == "deterministic theme summary"


def test_review_theme_summary_agent_preserves_prompt_identity() -> None:
    input_data = _summary_input()
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())

    result = agent.summarize(input_data)

    assert result.prompt_name == DEFAULT_REVIEW_THEME_PROMPT_NAME
    assert result.prompt_version == DEFAULT_REVIEW_THEME_PROMPT_VERSION


def test_review_theme_summary_agent_result_uses_fake_provider() -> None:
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())

    result = agent.summarize(_summary_input())

    assert result.model_provider == ModelProvider.FAKE


def test_review_theme_summary_agent_preserves_model_name() -> None:
    agent = ReviewThemeSummaryAgent(model_client=FakeModelClient(), model_name="fake-theme-model")

    result = agent.summarize(_summary_input())

    assert result.model_name == "fake-theme-model"


def test_review_theme_summary_agent_copies_token_and_cost_fields() -> None:
    agent = ReviewThemeSummaryAgent(
        model_client=FakeModelClient(
            input_tokens=11,
            output_tokens=7,
            estimated_cost_usd=Decimal("0.001"),
        )
    )

    result = agent.summarize(_summary_input())

    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.total_tokens == 18
    assert result.estimated_cost_usd == Decimal("0.001")


def test_review_theme_summary_agent_passes_budget_to_model_request() -> None:
    client = CapturingModelClient()
    budget = ModelBudget(max_total_tokens=100, allowed_providers=(ModelProvider.FAKE,))
    agent = ReviewThemeSummaryAgent(model_client=client)

    agent.summarize(_summary_input(budget=budget))

    assert client.request is not None
    assert client.request.budget == budget


def test_review_theme_summary_agent_loads_prompt_template() -> None:
    client = CapturingModelClient()
    agent = ReviewThemeSummaryAgent(model_client=client)

    agent.summarize(_summary_input())

    assert client.request is not None
    assert "ReadySetRentables Review Theme Summary" in client.request.input_text


def test_review_theme_summary_agent_input_text_includes_compact_fields() -> None:
    text = build_review_theme_summary_model_input_text(
        input_data=_summary_input(),
        prompt_text="Summarize themes.",
    )

    assert '"review_count": 3' in text
    assert '"average_rating": 4.5' in text
    assert '"rating_distribution":' in text
    assert '"5": 2' in text
    assert '"representative_reviews":' in text
    assert "Great location." in text
    assert "Easy check-in." in text


def test_review_theme_summary_agent_input_text_omits_unrelated_private_values() -> None:
    text = build_review_theme_summary_model_input_text(
        input_data=_summary_input(),
        prompt_text="Summarize themes.",
    )

    assert "password" not in text.lower()
    assert "api_key" not in text.lower()
    assert "connection string" not in text.lower()
    assert "private unrelated note" not in text.lower()


class CapturingModelClient:
    def __init__(self) -> None:
        self.request: ModelRequest | None = None

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.request = request
        return ModelResponse(
            invocation_id=uuid4(),
            status=ModelInvocationStatus.COMPLETED,
            provider=ModelProvider.FAKE,
            model_name=request.model_name,
            output_text="captured fake summary",
            input_tokens=4,
            output_tokens=3,
            total_tokens=7,
            estimated_cost_usd=Decimal("0"),
        )


def _summary_input(*, budget: ModelBudget | None = None) -> ReviewThemeSummaryInput:
    return ReviewThemeSummaryInput(
        run_id=uuid4(),
        review_count=3,
        average_rating=4.5,
        representative_reviews=["Great location.", "Easy check-in."],
        rating_distribution={"5": 2, "4": 1},
        budget=budget,
    )
