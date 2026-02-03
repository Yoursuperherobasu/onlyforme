import requests
from loguru import logger
from pydantic.v1 import SecretStr

from langbuilder.base.models.model import LCModelNode
from langbuilder.field_typing import LanguageModel
from langbuilder.field_typing.range_spec import RangeSpec
from langbuilder.io import DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput


class GroqModel(LCModelNode):
    display_name: str = "Groq"
    description: str = "Generate text using Groq."
    icon = "Groq"
    name = "GroqModel"

    inputs = [
        *LCModelNode._base_inputs,
        SecretStrInput(
            name="api_key", display_name="Groq API Key", info="API key for the Groq API.", real_time_refresh=True
        ),
        MessageTextInput(
            name="base_url",
            display_name="Groq API Base",
            info="Base URL path for API requests, leave blank if not using a proxy or service emulator.",
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
            info="Number of chat completions to generate for each prompt. "
            "Note that the API may not return the full n completions if duplicates are generated.",
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Enter API key to load available models.",
            options=[],
            value="",
            refresh_button=True,
            combobox=True,
        ),
    ]

    def _is_chat_model(self, model_data: dict) -> bool:
        """Check if model is a chat model (not TTS, STT, etc.) based on API response."""
        model_id = model_data.get("id", "").lower()
        # Filter out audio models (TTS, STT, whisper)
        audio_keywords = ["whisper", "tts", "speech", "audio"]
        return not any(keyword in model_id for keyword in audio_keywords)

    def get_models(self) -> list[str]:
        """Fetch available models from Groq API."""
        try:
            url = f"{self.base_url}/openai/v1/models"
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            
            # Filter to only chat models (exclude TTS, STT, whisper, etc.)
            model_ids = [
                model["id"] for model in model_list.get("data", []) 
                if self._is_chat_model(model)
            ]
            return model_ids
        except (ImportError, ValueError, requests.exceptions.RequestException) as e:
            logger.exception(f"Error getting model names: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"base_url", "model_name", "api_key"} and field_value:
            try:
                if len(self.api_key) != 0:
                    try:
                        ids = self.get_models()
                    except (ImportError, ValueError, requests.exceptions.RequestException) as e:
                        logger.exception(f"Error getting model names: {e}")
                        ids = []
                    build_config["model_name"]["options"] = ids
                    build_config["model_name"]["value"] = ids[0] if ids else ""
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
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
            api_key=SecretStr(self.api_key).get_secret_value(),
            streaming=self.stream,
        )
