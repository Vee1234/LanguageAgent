from dataclasses import dataclass
from cardModels.Card import Card
@dataclass(kw_only=True)
class LanguageUsageCard(Card):
    example: str
    emotional_colour: str
    usage_conditions: str
    notable_use: str
    lyric: str
