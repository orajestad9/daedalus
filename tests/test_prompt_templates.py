from pathlib import Path

import pytest

from daedalus.model_clients.prompts import load_prompt_template


PROMPT_NAME = "readysetrentables/review_theme_summary"
PROMPT_VERSION = "v0"
PROMPT_PATH = Path("prompts/readysetrentables/review_theme_summary/v0.md")


def test_committed_prompt_file_exists() -> None:
    assert PROMPT_PATH.is_file()


def test_load_prompt_template_loads_v0_prompt() -> None:
    template = load_prompt_template(prompt_name=PROMPT_NAME, prompt_version=PROMPT_VERSION)

    assert template.prompt_path == PROMPT_PATH.resolve()
    assert "review" in template.text.lower()


def test_load_prompt_template_preserves_prompt_identity() -> None:
    template = load_prompt_template(prompt_name=PROMPT_NAME, prompt_version=PROMPT_VERSION)

    assert template.prompt_name == PROMPT_NAME
    assert template.prompt_version == PROMPT_VERSION


def test_load_prompt_template_contains_non_empty_text() -> None:
    template = load_prompt_template(prompt_name=PROMPT_NAME, prompt_version=PROMPT_VERSION)

    assert template.text.strip()


def test_load_prompt_template_missing_prompt_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt_template(
            prompt_name="readysetrentables/missing_prompt",
            prompt_version=PROMPT_VERSION,
        )


def test_load_prompt_template_path_stays_under_prompts_root() -> None:
    prompts_root = Path("prompts")

    template = load_prompt_template(
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        prompts_root=prompts_root,
    )

    template.prompt_path.relative_to(prompts_root.resolve())


@pytest.mark.parametrize(
    ("prompt_name", "prompt_version"),
    [
        ("../secrets", PROMPT_VERSION),
        ("readysetrentables/../secrets", PROMPT_VERSION),
        (PROMPT_NAME, "../v0"),
    ],
)
def test_load_prompt_template_rejects_path_traversal(
    prompt_name: str,
    prompt_version: str,
) -> None:
    with pytest.raises(ValueError):
        load_prompt_template(prompt_name=prompt_name, prompt_version=prompt_version)


@pytest.mark.parametrize(
    ("prompt_name", "prompt_version"),
    [
        ("/tmp/secrets", PROMPT_VERSION),
        (PROMPT_NAME, "/tmp/v0"),
    ],
)
def test_load_prompt_template_rejects_absolute_paths(
    prompt_name: str,
    prompt_version: str,
) -> None:
    with pytest.raises(ValueError):
        load_prompt_template(prompt_name=prompt_name, prompt_version=prompt_version)
