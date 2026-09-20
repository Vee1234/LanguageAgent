import requests

ANKI_CONNECT_URL = "http://localhost:8765"


def invoke(action, **params):
    """Send one AnkiConnect request and return its `result`, raising on error."""
    payload = {"action": action, "version": 6, "params": params}
    response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("error") is not None:
        raise RuntimeError(f"AnkiConnect error: {data['error']}")
    return data["result"]


def create_model(model_name, fields, templates, css=""):
    return invoke(
        "createModel",
        modelName=model_name,
        inOrderFields=fields,
        css=css,
        cardTemplates=templates,
    )


# Order matches DESIGN.md §6.1 / assumption A7. Front = the target-language
# word only (Word); Back = every other field, each on its own line, with
# empty fields rendered as nothing via Anki's {{#Field}}...{{/Field}} sections.
VOCAB_FIELDS = [
    "Word",
    "Definition",
    "Example",
    "Register",
    "Connotations",
    "Implications",
    "Lyric",
    "Language",
]


def create_vocab_model(model_name="Vocab", fields=None, front_field="Word", card_fields=None):
    """One card template per field in card_fields (default: every field but
    front_field). Front: "{Word}: {FieldName}" — only rendered when that
    field is non-empty, so blank optional fields (Register, Lyric, ...)
    don't produce empty cards. Back: that field's value alone.
    """
    fields = fields or VOCAB_FIELDS
    back_fields = [f for f in fields if f != front_field]
    card_fields = back_fields if card_fields is None else card_fields

    templates = [
        {
            "Name": field,
            "Front": f"{{{{#{field}}}}}{{{{{front_field}}}}}: {field}{{{{/{field}}}}}",
            "Back": f"{{{{{field}}}}}",
        }
        for field in card_fields
    ]

    return create_model(
        model_name=model_name,
        fields=fields,
        css=".card { font-family: arial; font-size: 20px; text-align: left; }",
        templates=templates,
    )


def add_test_card(deck_name="new_deck"):
    note = {
        "deckName": deck_name,
        "modelName": "Basic",
        "fields": {
            "Front": "not a duplicate",
            "Back": "not duplicate",
        },
        "options": {
            "allowDuplicate": False,
            "duplicateScope": "deck",
        },
        "tags": ["ankiconnect-smoke-test"],
    }
    return invoke("addNote", note=note)


if __name__ == "__main__":
    note_id = add_test_card()
    print(f"Added note id: {note_id}")
