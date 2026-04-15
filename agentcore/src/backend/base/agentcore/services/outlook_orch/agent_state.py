"""Minimal AgentState shim for the ported MiBuddy `outlook_agent`.

MiBuddy is a LangGraph-based agent — `state` is a TypedDict shuttled
between nodes. agentcore doesn't use LangGraph for the orchestrator
chat flow, so we expose a plain `dict`-compatible `AgentState` plus the
two message helpers (`get_message_content`, `get_message_role`) that
`outlook_agent.py` imports.
"""
from __future__ import annotations

from typing import Any, Dict, TypedDict


class AgentState(TypedDict, total=False):
    """Ported from `MiBuddy-Backend/backend/agents/__init__.py`."""

    messages: list
    user_id: str
    final_response: str
    is_canvas_enabled: bool
    intent: str


def get_message_content(msg: Any) -> str:
    """Ported from `MiBuddy-Backend/backend/agents/utils.py`.

    Handles:
      - dicts with "content" key (our normal format)
      - objects with `.content` attribute (LangChain messages)
      - strings (fallback)
    """
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict):
        return str(msg.get("content") or "")
    return str(getattr(msg, "content", msg) or "")


def get_message_role(msg: Any) -> str:
    """Ported from MiBuddy — returns 'user' / 'assistant' / 'system'."""
    if msg is None:
        return ""
    if isinstance(msg, dict):
        return str(
            msg.get("role")
            or msg.get("sender")
            or ("assistant" if msg.get("sender") == "agent" else "")
            or "",
        )
    role = getattr(msg, "role", None) or getattr(msg, "type", None)
    return str(role or "")
