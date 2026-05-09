import pytest
from pydantic import ValidationError

from daedalus.model_clients import OllamaModelClientSettings


def test_ollama_settings_defaults_are_safe_and_local() -> None:
    settings = OllamaModelClientSettings()

    assert settings.enabled is False
    assert settings.base_url == "http://localhost:11434"
    assert settings.model_name
    assert settings.request_timeout_seconds > 0


@pytest.mark.parametrize("base_url", ["", "   "])
def test_ollama_settings_rejects_empty_base_url(base_url: str) -> None:
    with pytest.raises(ValidationError, match="base_url"):
        OllamaModelClientSettings(base_url=base_url)


@pytest.mark.parametrize("base_url", ["localhost:11434", "ftp://localhost:11434"])
def test_ollama_settings_rejects_invalid_base_url_scheme(base_url: str) -> None:
    with pytest.raises(ValidationError, match="http"):
        OllamaModelClientSettings(base_url=base_url)


@pytest.mark.parametrize("model_name", ["", "   "])
def test_ollama_settings_rejects_empty_model_name(model_name: str) -> None:
    with pytest.raises(ValidationError, match="model_name"):
        OllamaModelClientSettings(model_name=model_name)


@pytest.mark.parametrize("request_timeout_seconds", [0, -1])
def test_ollama_settings_rejects_non_positive_timeout(
    request_timeout_seconds: float,
) -> None:
    with pytest.raises(ValidationError, match="request_timeout_seconds"):
        OllamaModelClientSettings(request_timeout_seconds=request_timeout_seconds)


def test_ollama_settings_from_env_defaults_safely_when_variables_are_missing() -> None:
    settings = OllamaModelClientSettings.from_env({})

    assert settings == OllamaModelClientSettings()


def test_ollama_settings_from_env_reads_supported_non_secret_variables() -> None:
    settings = OllamaModelClientSettings.from_env(
        {
            "DAEDALUS_OLLAMA_ENABLED": "true",
            "DAEDALUS_OLLAMA_BASE_URL": "http://localhost:11435",
            "DAEDALUS_OLLAMA_MODEL": "llama-local",
            "DAEDALUS_OLLAMA_TIMEOUT_SECONDS": "12.5",
        }
    )

    assert settings.enabled is True
    assert settings.base_url == "http://localhost:11435"
    assert settings.model_name == "llama-local"
    assert settings.request_timeout_seconds == 12.5


def test_ollama_settings_from_env_reads_false_enabled_value() -> None:
    settings = OllamaModelClientSettings.from_env({"DAEDALUS_OLLAMA_ENABLED": "off"})

    assert settings.enabled is False


def test_ollama_settings_from_env_rejects_invalid_enabled_value() -> None:
    with pytest.raises(ValueError, match="Invalid Ollama enabled value"):
        OllamaModelClientSettings.from_env({"DAEDALUS_OLLAMA_ENABLED": "maybe"})


def test_ollama_settings_from_env_rejects_invalid_timeout_value() -> None:
    with pytest.raises(ValueError):
        OllamaModelClientSettings.from_env({"DAEDALUS_OLLAMA_TIMEOUT_SECONDS": "not-a-number"})
