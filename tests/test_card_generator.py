from unittest.mock import patch

import pytest

import constants
from cardGenerators.LanguageUsageCardGenerator import LanguageUsageCardGenerator
from cardModels.LanguageUsageCard import LanguageUsageCard


@pytest.fixture
def generator():
    # Replace the real Gemini client so no network call or API key is needed.
    with patch("cardGenerators.CardGenerator.GeminiClient") as client_cls:
        gen = LanguageUsageCardGenerator("French")
        yield gen
        client_cls.assert_called_once_with()


def test_system_context_is_formatted_with_language(generator):
    assert generator.system_context == constants.system_context.format(language="French")
    assert "{language}" not in generator.system_context


def test_get_definition_sends_formatted_prompt(generator):
    generator.client.send_prompt.return_value = "Bâtiment d'habitation."

    result = generator.get_definition("maison")

    assert result == "Bâtiment d'habitation."
    generator.client.send_prompt.assert_called_once_with(
        constants.definition_prompt.format(word="maison", language="French"),
        generator.system_context,
    )


@pytest.mark.parametrize(
    "method, prompt",
    [
        ("get_example", constants.example_prompt),
        ("get_emotional_colour", constants.emotional_colour_prompt),
        ("get_usage_conditions", constants.usage_conditions_prompt),
        ("get_lyric", constants.lyric_prompt),
        ("get_notable_use", constants.notable_use_prompt),
    ],
)
def test_each_field_uses_its_own_prompt(generator, method, prompt):
    generator.client.send_prompt.return_value = "réponse"

    assert getattr(generator, method)("maison") == "réponse"
    generator.client.send_prompt.assert_called_once_with(
        prompt.format(word="maison", language="French"),
        generator.system_context,
    )


@pytest.mark.parametrize("reply", ["NONE", " NONE\n", constants.none_response])
def test_notable_use_none_becomes_empty_string(generator, reply):
    generator.client.send_prompt.return_value = reply
    assert generator.get_notable_use("maison") == ""


def test_notable_use_keeps_real_quote(generator):
    generator.client.send_prompt.return_value = "« Ma maison, c'est ta maison »"
    assert generator.get_notable_use("maison") == "« Ma maison, c'est ta maison »"


def test_generate_card_fills_every_field(generator):
    replies = {
        constants.definition_prompt: "def",
        constants.example_prompt: "ex",
        constants.emotional_colour_prompt: "colour",
        constants.usage_conditions_prompt: "usage",
        constants.notable_use_prompt: "NONE",
        constants.lyric_prompt: "lyric",
    }
    by_prompt = {p.format(word="maison", language="French"): r for p, r in replies.items()}
    generator.client.send_prompt.side_effect = lambda prompt, _ctx: by_prompt[prompt]

    card = generator.generate_card("maison")

    assert card == LanguageUsageCard(
        word="maison",
        language="French",
        definition="def",
        example="ex",
        emotional_colour="colour",
        usage_conditions="usage",
        notable_use="",
        lyric="lyric",
    )
    assert generator.client.send_prompt.call_count == len(replies)
