from pathlib import Path

import pytest

from daedalus.cli import main


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")


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

    output = capsys.readouterr().out
    assert "metadata=" in output
    assert "run_id=" in output
