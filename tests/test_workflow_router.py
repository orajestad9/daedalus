from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.orchestrator.workflow_router import (
    UnsupportedWorkflowError,
    WorkflowApprovalRequiredError,
    run_workflow_from_manifest_path,
)
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.shared.workflow_manifest import WorkflowExecutionEngine


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")
LANGGRAPH_SAMPLE_MANIFEST_PATH = Path(
    "workflows/readysetrentables_review_normalization_langgraph.yaml"
)
EXPECTED_STEP_NAMES = [
    "load_reviews",
    "write_normalized_artifact",
    "write_metadata_artifact",
    "write_summary_artifact",
    "write_run_record_artifact",
    "build_review_theme_summary_input",
    "run_fake_review_theme_summary_agent",
    "write_review_theme_summary_artifact",
]


def test_run_workflow_from_committed_manifest_succeeds() -> None:
    result = run_workflow_from_manifest_path(SAMPLE_MANIFEST_PATH)

    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.run_record_json_path.is_file()
    assert result.review_count == 8
    assert result.approval_required is False
    assert result.approved is False


def test_committed_deterministic_manifest_routes_deterministic_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_deterministic(**_: object) -> ReviewNormalizationWorkflowResult:
        calls.append("deterministic")
        return _workflow_result(Path("artifacts/test/normalized_reviews.json"))

    def fake_langgraph(**_: object) -> object:
        calls.append("langgraph")
        msg = "LangGraph runner should not be called for deterministic manifest"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_review_normalization_workflow",
        fake_deterministic,
    )
    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_readysetrentables_review_graph",
        fake_langgraph,
    )

    result = run_workflow_from_manifest_path(SAMPLE_MANIFEST_PATH)

    assert calls == ["deterministic"]
    assert result.review_count == 8


def test_run_workflow_from_langgraph_manifest_succeeds() -> None:
    result = run_workflow_from_manifest_path(LANGGRAPH_SAMPLE_MANIFEST_PATH)

    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.run_record_json_path.is_file()
    assert result.review_count == 8
    assert [step.step_name for step in result.steps] == EXPECTED_STEP_NAMES


def test_langgraph_manifest_routes_graph_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
        execution_engine="langgraph",
    )
    calls: list[str] = []

    def fake_deterministic(**_: object) -> ReviewNormalizationWorkflowResult:
        calls.append("deterministic")
        msg = "Deterministic runner should not be called for LangGraph manifest"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_review_normalization_workflow",
        fake_deterministic,
    )

    result = run_workflow_from_manifest_path(manifest_path)

    assert calls == []
    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.run_record_json_path.is_file()
    assert [step.step_name for step in result.steps] == EXPECTED_STEP_NAMES


def test_deterministic_manifest_with_langgraph_override_routes_graph_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
        execution_engine="deterministic",
    )
    calls: list[str] = []

    def fake_deterministic(**_: object) -> ReviewNormalizationWorkflowResult:
        calls.append("deterministic")
        msg = "Deterministic runner should not be called when LangGraph is overridden"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_review_normalization_workflow",
        fake_deterministic,
    )

    result = run_workflow_from_manifest_path(
        manifest_path,
        execution_engine_override=WorkflowExecutionEngine.LANGGRAPH,
    )

    assert calls == []
    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.run_record_json_path.is_file()
    assert [step.step_name for step in result.steps] == EXPECTED_STEP_NAMES


def test_langgraph_manifest_with_deterministic_override_routes_deterministic_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
        execution_engine="langgraph",
    )
    calls: list[str] = []

    def fake_deterministic(**_: object) -> ReviewNormalizationWorkflowResult:
        calls.append("deterministic")
        return _workflow_result(tmp_path / "normalized_reviews.json")

    def fake_langgraph(**_: object) -> object:
        msg = "LangGraph runner should not be called when deterministic is overridden"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_review_normalization_workflow",
        fake_deterministic,
    )
    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_readysetrentables_review_graph",
        fake_langgraph,
    )

    result = run_workflow_from_manifest_path(
        manifest_path,
        execution_engine_override=WorkflowExecutionEngine.DETERMINISTIC,
    )

    assert calls == ["deterministic"]
    assert result.review_count == 8


def test_approval_gate_still_applies_with_execution_engine_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
        execution_engine="deterministic",
    )

    def fail_if_called(**_: object) -> object:
        msg = "Workflow runner should not be called before approval"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_review_normalization_workflow",
        fail_if_called,
    )
    monkeypatch.setattr(
        "daedalus.orchestrator.workflow_router.run_readysetrentables_review_graph",
        fail_if_called,
    )

    with pytest.raises(WorkflowApprovalRequiredError, match="requires human approval"):
        run_workflow_from_manifest_path(
            manifest_path,
            execution_engine_override=WorkflowExecutionEngine.LANGGRAPH,
        )


def test_run_workflow_from_manifest_requires_approval(tmp_path: Path) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    with pytest.raises(WorkflowApprovalRequiredError, match="requires human approval"):
        run_workflow_from_manifest_path(manifest_path)


def test_run_workflow_from_approved_manifest_succeeds(tmp_path: Path) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    result = run_workflow_from_manifest_path(manifest_path, approved=True)

    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.run_record_json_path.is_file()
    assert result.approval_required is True
    assert result.approved is True

    summary = result.summary_markdown_path.read_text(encoding="utf-8")
    assert "Approval required: True" in summary
    assert "Approved: True" in summary


def test_run_workflow_from_manifest_rejects_unsupported_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "unsupported.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: unsupported_workflow",
                "domain: unsupported_domain",
                "description: Unsupported test workflow.",
                f"input_csv_path: {SAMPLE_CSV_PATH}",
                "output_json_path: artifacts/unsupported/output.json",
                "requires_human_approval: false",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedWorkflowError, match="unsupported_workflow"):
        run_workflow_from_manifest_path(manifest_path)


def _write_readysetrentables_manifest(
    tmp_path: Path,
    *,
    requires_human_approval: bool,
    execution_engine: str | None = None,
) -> Path:
    output_path = tmp_path / "normalized_reviews.json"
    manifest_path = tmp_path / "readysetrentables.yaml"
    lines = [
        "workflow_name: readysetrentables_review_normalization",
        "domain: readysetrentables_reviews",
        "description: Approval gate test workflow.",
        f"input_csv_path: {SAMPLE_CSV_PATH}",
        f"output_json_path: {output_path}",
        f"requires_human_approval: {str(requires_human_approval).lower()}",
    ]
    if execution_engine is not None:
        lines.append(f"execution_engine: {execution_engine}")

    manifest_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return manifest_path


def _workflow_result(output_json_path: Path) -> ReviewNormalizationWorkflowResult:
    run_id = uuid4()
    return ReviewNormalizationWorkflowResult(
        source_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        metadata_json_path=output_json_path.with_name(f"{output_json_path.stem}.metadata.json"),
        summary_markdown_path=output_json_path.with_name(f"{output_json_path.stem}.summary.md"),
        run_record_json_path=output_json_path.with_name(f"{output_json_path.stem}.run.json"),
        review_count=8,
        run_id=run_id,
        approval_required=False,
        approved=False,
        steps=[WorkflowStepRecord.start(run_id=run_id, step_name="load_reviews").complete()],
    )
