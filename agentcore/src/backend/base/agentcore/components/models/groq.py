import requests
from loguru import logger
from pydantic.v1 import SecretStr

from agentcore.base.models.model import LCModelNode
from agentcore.field_typing import LanguageModel
from agentcore.field_typing.range_spec import RangeSpec
from agentcore.io import DropdownInput, IntInput, MessageTextInput, SliderInput


GROQ_API_KEY = ""



class GroqModel(LCModelNode):
    display_name: str = "Groq"
    description: str = "Generate text using Groq."
    icon = "Groq"
    name = "GroqModel"

    inputs = [
        *LCModelNode._base_inputs,
        MessageTextInput(
            name="base_url",
            display_name="Groq API Base",
            info="Base URL path for API requests.",
            advanced=True,
            value="https://api.groq.com",
            real_time_refresh=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate.",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="n",
            display_name="N",
            info="Number of chat completions to generate for each prompt.",
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Select a Groq model.",
            options=[],
            value="",
            refresh_button=True,
            combobox=True,
        ),
    ]

    def _is_chat_model(self, model_data: dict) -> bool:
        model_id = model_data.get("id", "").lower()
        audio_keywords = ["whisper", "tts", "speech", "audio"]
        return not any(keyword in model_id for keyword in audio_keywords)

    def get_models(self) -> list[str]:
        try:
            url = f"{self.base_url}/openai/v1/models"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            model_ids = [
                model["id"] for model in model_list.get("data", [])
                if self._is_chat_model(model)
            ]
            return model_ids
        except (ImportError, ValueError, requests.exceptions.RequestException) as e:
            logger.exception(f"Error getting model names: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"base_url", "model_name"} and field_value:
            try:
                ids = self.get_models()
                build_config["model_name"]["options"] = ids
                build_config["model_name"]["value"] = ids[0] if ids else ""
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_model(self) -> LanguageModel:
        try:
            from langchain_groq import ChatGroq
        except ImportError as e:
            msg = "langchain-groq is not installed. Please install it with `pip install langchain-groq`."
            raise ImportError(msg) from e

        return ChatGroq(
            model=self.model_name,
            max_tokens=self.max_tokens or None,
            temperature=self.temperature,
            base_url=self.base_url,
            n=self.n or 1,
            api_key=GROQ_API_KEY,
            streaming=self.stream,
        )
