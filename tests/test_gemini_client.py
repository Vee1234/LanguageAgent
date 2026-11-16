from types import SimpleNamespace
from unittest.mock import patch

import pytest

from GeminiClient import GeminiClient


@pytest.fixture
def client():
    with patch("GeminiClient.genai.Client") as client_cls:
        yield GeminiClient(), client_cls.return_value


def interaction(status="completed", text="bonjour"):
    return SimpleNamespace(status=status, output_text=text)


def test_send_prompt_returns_output_text(client):
    gemini, sdk = client
    sdk.interactions.create.return_value = interaction(text="maison")

    assert gemini.send_prompt("prompt") == "maison"
    sdk.interactions.create.assert_called_once_with(
        model=gemini.model,
        input="prompt",
        generation_config={"seed": 0},
    )


def test_send_prompt_passes_system_context_when_given(client):
    gemini, sdk = client
    sdk.interactions.create.return_value = interaction()

    gemini.send_prompt("prompt", system_context="ctx")

    assert sdk.interactions.create.call_args.kwargs["system_instruction"] == "ctx"


def test_send_prompt_omits_system_instruction_by_default(client):
    gemini, sdk = client
    sdk.interactions.create.return_value = interaction()

    gemini.send_prompt("prompt")

    assert "system_instruction" not in sdk.interactions.create.call_args.kwargs


@pytest.mark.parametrize(
    "result",
    [interaction(status="failed"), interaction(text=None)],
    ids=["not-completed", "no-text"],
)
def test_send_prompt_raises_when_no_usable_text(client, result):
    gemini, sdk = client
    sdk.interactions.create.return_value = result

    with pytest.raises(RuntimeError, match="no text"):
        gemini.send_prompt("prompt")
