"""Versioned prompt template loading for future model-client usage."""

from pathlib import Path

from pydantic import BaseModel


class PromptTemplate(BaseModel):
    """A committed prompt template loaded by stable name and version."""

    prompt_name: str
    prompt_version: str
    prompt_path: Path
    text: str


def load_prompt_template(
    *,
    prompt_name: str,
    prompt_version: str,
    prompts_root: Path = Path("prompts"),
) -> PromptTemplate:
    """Load a UTF-8 prompt template by versioned prompt identity.

    Prompt names may use slash-separated repository paths such as
    `readysetrentables/review_theme_summary`, but absolute paths and traversal
    segments are rejected before reading from disk.
    """
    _validate_prompt_path_part(prompt_name, "prompt_name")
    _validate_prompt_path_part(prompt_version, "prompt_version")

    root = prompts_root.resolve()
    prompt_path = root.joinpath(*prompt_name.split("/"), f"{prompt_version}.md").resolve()
    prompt_path.relative_to(root)

    return PromptTemplate(
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        prompt_path=prompt_path,
        text=prompt_path.read_text(encoding="utf-8"),
    )


def _validate_prompt_path_part(value: str, field_name: str) -> None:
    path = Path(value)
    if path.is_absolute():
        msg = f"{field_name} must be relative"
        raise ValueError(msg)
    if ".." in path.parts:
        msg = f"{field_name} must not contain path traversal segments"
        raise ValueError(msg)
