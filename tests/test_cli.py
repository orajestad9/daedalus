from pathlib import Path

import pytest

from daedalus.cli import main


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")


def test_normalize_reviews_command_succeeds_with_sample_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    exit_code = main(
        [
            "normalize-reviews",
            "--input",
            str(SAMPLE_CSV_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()
    assert (tmp_path / "normalized_reviews.metadata.json").is_file()
    assert (tmp_path / "normalized_reviews.summary.md").is_file()

    output = capsys.readouterr().out
    assert "metadata=" in output
    assert "summary=" in output
    assert "run_id=" in output


def test_run_workflow_command_succeeds_with_sample_manifest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(SAMPLE_MANIFEST_PATH),
        ]
    )

    output_path = Path("artifacts/readysetrentables/normalized_reviews.json")
    metadata_path = Path("artifacts/readysetrentables/normalized_reviews.metadata.json")
    summary_path = Path("artifacts/readysetrentables/normalized_reviews.summary.md")

    assert exit_code == 0
    assert output_path.is_file()
    assert metadata_path.is_file()
    assert summary_path.is_file()

    output = capsys.readouterr().out
    assert "run_id=" in output
    assert "review_count=8" in output
    assert f"output={output_path}" in output
    assert f"metadata={metadata_path}" in output
    assert f"summary={summary_path}" in output


def test_run_workflow_command_rejects_unsupported_manifest(tmp_path: Path) -> None:
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

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-workflow",
                "--manifest",
                str(manifest_path),
            ]
        )

    assert exc_info.value.code == 2
