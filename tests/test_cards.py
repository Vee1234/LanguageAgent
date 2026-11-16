import dataclasses

import pytest

from cardModels.Card import Card
from cardModels.LanguageUsageCard import LanguageUsageCard

USAGE_FIELDS = dict(
    word="maison",
    language="French",
    definition="Bâtiment d'habitation.",
    example="Ma maison est grande.",
    emotional_colour="chaleur, sécurité",
    usage_conditions="courant, tous registres",
    notable_use="",
    lyric="",
)


def test_language_usage_card_is_a_card():
    card = LanguageUsageCard(**USAGE_FIELDS)
    assert isinstance(card, Card)
    assert card.word == "maison"
    assert card.lyric == ""


def test_language_usage_card_rejects_positional_args():
    with pytest.raises(TypeError):
        LanguageUsageCard(*USAGE_FIELDS.values())


def test_language_usage_card_requires_every_field():
    missing_lyric = {k: v for k, v in USAGE_FIELDS.items() if k != "lyric"}
    with pytest.raises(TypeError):
        LanguageUsageCard(**missing_lyric)


def test_field_order_base_fields_first():
    names = [f.name for f in dataclasses.fields(LanguageUsageCard)]
    assert names[:3] == ["word", "language", "definition"]
    assert set(names) == set(USAGE_FIELDS)
