from unittest.mock import patch

import pytest

import AnkiConnection


@pytest.fixture
def post():
    with patch("AnkiConnection.requests.post") as mock_post:
        yield mock_post


def respond(post, result=None, error=None):
    post.return_value.json.return_value = {"result": result, "error": error}


def test_invoke_sends_versioned_payload_and_returns_result(post):
    respond(post, result=123)

    assert AnkiConnection.invoke("deckNames", foo="bar") == 123
    post.assert_called_once_with(
        AnkiConnection.ANKI_CONNECT_URL,
        json={"action": "deckNames", "version": 6, "params": {"foo": "bar"}},
        timeout=10,
    )
    post.return_value.raise_for_status.assert_called_once_with()


def test_invoke_raises_on_anki_error(post):
    respond(post, error="deck was not found")

    with pytest.raises(RuntimeError, match="deck was not found"):
        AnkiConnection.invoke("addNote")


def test_create_vocab_model_one_template_per_back_field(post):
    respond(post, result="ok")

    AnkiConnection.create_vocab_model()

    params = post.call_args.kwargs["json"]["params"]
    assert params["modelName"] == "Vocab"
    assert params["inOrderFields"] == AnkiConnection.VOCAB_FIELDS
    names = [t["Name"] for t in params["cardTemplates"]]
    assert names == [f for f in AnkiConnection.VOCAB_FIELDS if f != "Word"]


def test_vocab_template_only_renders_when_field_is_filled(post):
    respond(post, result="ok")

    AnkiConnection.create_vocab_model(card_fields=["Definition"])

    (template,) = post.call_args.kwargs["json"]["params"]["cardTemplates"]
    assert template == {
        "Name": "Definition",
        "Front": "{{#Definition}}{{Word}}: Definition{{/Definition}}",
        "Back": "{{Definition}}",
    }
