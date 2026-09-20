# API Shapes

Field reference for the data objects passed between components. Generators are out of scope — this covers only the things they produce and consume.

## Vocab

`Vocab.py` — the input to card generation. A plain class, not a dataclass; fields are set in `__init__` and read through getters.

| Field | Type | Access |
|---|---|---|
| `word` | `str` | `get_word()` |
| `language` | `str` | `get_language()` |

```python
Vocab(word="felicidad", language="Spanish")
```

Positional construction works: `Vocab("felicidad", "Spanish")`.

## Card

`cardModels/Card.py` — abstract base. Every card carries the vocab it was generated from plus a definition.

| Field | Type |
|---|---|
| `vocab` | `Vocab` |
| `definition` | `str` |

`@dataclass(kw_only=True)`, so it cannot be constructed positionally. Abstract — instantiate a subclass.

## LanguageUsageCard

`cardModels/LanguageUsageCard.py` — extends `Card`. Seven fields total, all `str` except the inherited `vocab`.

| Field | Type | Source |
|---|---|---|
| `vocab` | `Vocab` | inherited from `Card` |
| `definition` | `str` | inherited from `Card` |
| `example` | `str` | the word used in a short sentence |
| `emotional_colour` | `str` | feelings the word evokes |
| `usage_conditions` | `str` | when the word applies |
| `implication` | `str` | |
| `lyric` | `str` | |

Inherited fields come first in field order — base-class fields always precede subclass ones.

```python
LanguageUsageCard(
    vocab=vocab,
    definition=...,
    example=...,
    emotional_colour=...,
    usage_conditions=...,
    implication=...,
    lyric=...,
)
```

## Construction rules

Both card classes are `@dataclass(kw_only=True)`. `kw_only` is **not** inherited — it applies only to fields declared in the class carrying the decorator, so any new `Card` subclass needs its own `kw_only=True` or its fields will be positional.

The reason for keyword-only: six of the seven fields are `str`, so a transposed pair would otherwise be accepted silently and surface later as a card with a lyric in the definition slot.
