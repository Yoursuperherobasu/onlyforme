"""Image generation handler for orchestrator.

Routes image generation requests to a configurable model from the registry
via the Model microservice.
"""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agentcore.services.model_service_client import MicroserviceChatModel

logger = logging.getLogger(__name__)

IMAGE_GEN_SYSTEM_PROMPT = (
    "You are an image generation assistant. When the user asks you to create, "
    "generate, draw, or render an image, generate it using your image generation "
    "capabilities. Describe what you generated and provide the image."
)


def _get_image_gen_model_id() -> str:
    """Get the image generation model ID from settings."""
    from agentcore.services.deps import get_settings_service
    settings = get_settings_service()
    model_id = settings.settings.image_gen_model_id
    if not model_id:
        raise ValueError("Image generation model not configured. Set IMAGE_GEN_MODEL_ID in settings.")
    return model_id


def _build_image_model(model_id: str) -> MicroserviceChatModel:
    """Create a MicroserviceChatModel for image generation."""
    from agentcore.services.deps import get_settings_service
    settings = get_settings_service()

    return MicroserviceChatModel(
        service_url=settings.settings.model_service_url,
        service_api_key=settings.settings.model_service_api_key,
        registry_model_id=model_id,
        provider="openai",  # placeholder — resolved from registry by model service
        model=f"image-gen-{model_id[:8]}",
    )


async def handle_image_generation(query: str) -> dict:
    """Call image generation model and return the response.

    Returns dict with keys: response_text, model_name
    """
    try:
        model_id = _get_image_gen_model_id()
        model = _build_image_model(model_id)

        messages = [
            SystemMessage(content=IMAGE_GEN_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]

        result = await model.ainvoke(messages)
        response_text = result.content if hasattr(result, "content") else str(result)
        metadata = getattr(result, "response_metadata", {}) or {}

        return {
            "response_text": response_text,
            "model_name": metadata.get("model_name", "image-generation"),
        }

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return {
            "response_text": "Image generation encountered an error. Please try again.",
            "model_name": "image-generation",
        }


async def handle_image_generation_stream(
    query: str,
    event_manager=None,
) -> dict:
    """Stream image generation response, forwarding tokens to event_manager.

    Returns dict with keys: response_text, model_name
    """
    try:
        model_id = _get_image_gen_model_id()
        model = _build_image_model(model_id)

        messages = [
            SystemMessage(content=IMAGE_GEN_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]

        full_response = ""
        model_name = "image-generation"

        async for chunk in model.astream(messages):
            msg = chunk.message if hasattr(chunk, "message") else chunk
            content = getattr(msg, "content", "")
            metadata = getattr(msg, "response_metadata", {}) or {}

            if content:
                full_response += content
                if event_manager:
                    event_manager.on_token(data={"chunk": content})

            if metadata.get("model_name"):
                model_name = metadata["model_name"]

        return {
            "response_text": full_response,
            "model_name": model_name,
        }

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Image generation stream failed: {e}")
        error_msg = "Image generation encountered an error. Please try again."
        if event_manager:
            event_manager.on_token(data={"chunk": error_msg})
        return {
            "response_text": error_msg,
            "model_name": "image-generation",
        }
