"""LTM Conversation Summarizer.

Uses an LLM (from settings config or passed directly) to summarize
conversation history into concise paragraphs for long-term storage.
"""

from __future__ import annotations

from loguru import logger

from agentcore.schema.message import Message

SUMMARIZATION_PROMPT = """\
You are a conversation summarizer. Summarize the following conversation between \
a user and an AI assistant into a concise paragraph. Capture the key topics discussed, \
questions asked, decisions made, important context, and any facts or preferences revealed. \
Keep the summary under {max_tokens} tokens.

Conversation:
{conversation_text}

Concise Summary:"""


_cached_registry_model_id: str | None = None


def _get_ltm_llm():
    """Build a MicroserviceChatModel from LTM settings.

    Auto-discovers the registry_model_id by looking up the provider/model
    in the Model Registry (same way the LLM component does).
    """
    global _cached_registry_model_id

    from agentcore.services.deps import get_settings_service
    from agentcore.services.model_service_client import MicroserviceChatModel, _get_model_service_settings

    settings = get_settings_service().settings
    service_url, service_api_key = _get_model_service_settings()

    registry_id = settings.ltm_llm_registry_model_id or _cached_registry_model_id

    # Auto-discover registry_model_id from the Model Registry
    if not registry_id and settings.ltm_llm_provider:
        try:
            from agentcore.services.model_service_client import fetch_registry_models

            # First try filtering by provider
            models = fetch_registry_models(
                provider=settings.ltm_llm_provider,
                model_type="llm",
                active_only=True,
            )
            logger.info(f"[LTM] Registry lookup: provider={settings.ltm_llm_provider}, found {len(models)} models")

            # If no results with provider filter, try all models
            if not models:
                models = fetch_registry_models(model_type="llm", active_only=True)
                logger.info(f"[LTM] Registry lookup (all providers): found {len(models)} models")

            # Find matching model by name
            for m in models:
                model_name = m.get("model_name", "") or m.get("name", "")
                if model_name == settings.ltm_llm_model:
                    registry_id = str(m.get("id", ""))
                    _cached_registry_model_id = registry_id
                    logger.info(f"[LTM] Auto-discovered registry_model_id={registry_id} for {model_name}")
                    break

            # If no exact match, try partial match
            if not registry_id:
                for m in models:
                    model_name = m.get("model_name", "") or m.get("name", "")
                    if settings.ltm_llm_model and settings.ltm_llm_model in model_name:
                        registry_id = str(m.get("id", ""))
                        _cached_registry_model_id = registry_id
                        logger.info(f"[LTM] Partial match: registry_model_id={registry_id} for {model_name}")
                        break

            # Last resort — use first model from the provider
            if not registry_id and models:
                registry_id = str(models[0].get("id", ""))
                _cached_registry_model_id = registry_id
                first_name = models[0].get("model_name", "") or models[0].get("name", "")
                logger.info(f"[LTM] Using first available: {first_name} (id={registry_id})")

            # Fallback: query the DB directly
            if not registry_id:
                try:
                    from agentcore.services.deps import get_db_service
                    from sqlalchemy import text as sa_text

                    db_service = get_db_service()
                    with db_service.engine.connect() as conn:
                        result = conn.execute(sa_text(
                            "SELECT id, model_name, provider FROM model_registry "
                            "WHERE is_active = true AND model_type = 'llm' "
                            "AND provider = :provider ORDER BY created_at DESC LIMIT 5"
                        ), {"provider": settings.ltm_llm_provider})
                        rows = result.fetchall()
                        logger.info(f"[LTM] DB lookup found {len(rows)} models for provider={settings.ltm_llm_provider}")
                        for row in rows:
                            if settings.ltm_llm_model and settings.ltm_llm_model in (row[1] or ""):
                                registry_id = str(row[0])
                                _cached_registry_model_id = registry_id
                                logger.info(f"[LTM] DB match: registry_model_id={registry_id} for {row[1]}")
                                break
                        if not registry_id and rows:
                            registry_id = str(rows[0][0])
                            _cached_registry_model_id = registry_id
                            logger.info(f"[LTM] DB fallback: using {rows[0][1]} (id={registry_id})")
                except Exception as db_err:
                    logger.warning(f"[LTM] DB lookup failed: {db_err}")

            if not registry_id:
                logger.warning("[LTM] No models found in registry! Make sure you've registered a model.")
        except Exception as e:
            logger.warning(f"[LTM] Could not auto-discover registry model: {e}")

    return MicroserviceChatModel(
        service_url=service_url,
        service_api_key=service_api_key,
        provider=settings.ltm_llm_provider,
        model=settings.ltm_llm_model,
        registry_model_id=registry_id or None,
    )


def _format_messages(messages: list[Message]) -> str:
    """Format a list of Message objects into conversation text."""
    lines = []
    for msg in messages:
        sender = msg.sender_name or msg.sender or "Unknown"
        text = msg.text or ""
        lines.append(f"{sender}: {text}")
    return "\n".join(lines)


async def summarize_conversation(messages: list[Message], llm=None, max_tokens: int = 500) -> str:
    """Summarize a list of conversation messages.

    Args:
        messages: List of Message objects (both user and AI messages).
        llm: Optional LangChain BaseChatModel. If None, uses LTM settings to create one.
        max_tokens: Target max tokens for the summary.

    Returns:
        A concise summary string.
    """
    if not messages:
        return ""

    if llm is None:
        llm = _get_ltm_llm()

    conversation_text = _format_messages(messages)
    prompt = SUMMARIZATION_PROMPT.format(conversation_text=conversation_text, max_tokens=max_tokens)

    try:
        response = await llm.ainvoke(prompt)
        summary = response.content if hasattr(response, "content") else str(response)
        summary = summary.strip()
        logger.info(f"[LTM] Summarized {len(messages)} messages into {len(summary)} chars")
        logger.info(f"[LTM] === SUMMARY OUTPUT ===\n{summary}\n=== END SUMMARY ==="  )
        return summary
    except Exception as e:
        logger.error(f"[LTM] Summarization failed: {e}")
        raise
