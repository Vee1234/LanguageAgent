from cardGenerators.CardGenerator import CardGenerator
from cardModels.LanguageUsageCard import LanguageUsageCard
from constants import *

class LanguageUsageCardGenerator(CardGenerator):

    def generate_card(self, word: str) -> LanguageUsageCard:
        '''orchestrator method'''
        return LanguageUsageCard(
            word = word,
            language = self.language,
            definition = self.get_definition(word),
            example = self.get_example(word),
            emotional_colour = self.get_emotional_colour(word),
            usage_conditions = self.get_usage_conditions(word),
            notable_use = self.get_notable_use(word),
            lyric = self.get_lyric(word),
        )

    def get_example(self, word: str) -> str:
        return self.client.send_prompt(example_prompt.format(word = word, language = self.language))

    def get_emotional_colour(self, word: str) -> str:
        return self.client.send_prompt(emotional_colour_prompt.format(word = word, language = self.language))

    def get_usage_conditions(self, word: str) -> str:
        return self.client.send_prompt(usage_conditions_prompt.format(word = word, language = self.language))

    def get_lyric(self, word: str) -> str:
        return self.client.send_prompt(lyric_prompt.format(word = word, language = self.language))

    def get_notable_use(self, word: str) -> str:
        use = self.client.send_prompt(notable_use_prompt.format(word = word, language = self.language))
        return "" if use.strip() == "NONE" else use
