from google import genai
from google.genai import types
from constants import *

class GeminiClient:
    def __init__(self, language: str):
        self.system_context = system_context.format(language = language)
        self.client = genai.Client()
        self.model = "gemini-3.1-flash-lite"

    def send_prompt(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model = self.model,
            contents = prompt,
            config = types.GenerateContentConfig(
                system_instruction = self.system_context,
                temperature = 0,
            ),
        )
        if response.text is None:
            finish_reason = response.candidates[0].finish_reason if response.candidates else None
            raise RuntimeError(
                f"Model returned no text (finish_reason={finish_reason}, "
                f"prompt_feedback={response.prompt_feedback})"
            )
        return response.text
