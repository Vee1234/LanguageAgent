from dataclasses import dataclass
from abc import ABC
@dataclass(kw_only=True)
class Card(ABC):
    word: str
    language: str
    definition: str
