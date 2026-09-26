from abc import ABC, abstractmethod
from cardModels.Card import Card
from GeminiClient import GeminiClient
from constants import *

class CardGenerator(ABC):
    '''Base class for all card generators'''

    def __init__(self, language: str):
        self.language = language
        self.system_context = system_context.format(language = language)
        self.client = GeminiClient()

    @abstractmethod
    def generate_card(self, word: str) -> Card:
        '''Generates a card depending on the spec provided'''

    def get_definition(self, word: str) -> str:
        return self.client.send_prompt(definition_prompt.format(word = word, language = self.language), self.system_context)
