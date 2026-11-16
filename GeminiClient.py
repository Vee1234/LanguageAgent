from google import genai

class GeminiClient:
    def __init__(self):
        self.client = genai.Client()
        self.model = "gemini-3.1-flash-lite"

    def send_prompt(self, prompt: str, system_context: str | None = None) -> str:
        optional_args = {} if system_context is None else {"system_instruction": system_context}
        interaction = self.client.interactions.create(
            model = self.model,
            input = prompt,
            generation_config = {"seed": 0},
            **optional_args,
        )
        if interaction.status != "completed" or interaction.output_text is None:
            raise RuntimeError(
                f"Model returned no text (status={interaction.status})"
            )
        return interaction.output_text
