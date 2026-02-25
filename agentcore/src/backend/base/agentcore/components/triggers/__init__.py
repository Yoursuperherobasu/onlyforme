from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentcore.components._importing import import_mod

if TYPE_CHECKING:
    from agentcore.components.triggers.schedule_trigger import ScheduleTrigger
    from agentcore.components.triggers.folder_monitor import FolderMonitor
    from agentcore.components.triggers.email_trigger import EmailTrigger

_dynamic_imports = {
    "ScheduleTrigger": "schedule_trigger",
    "FolderMonitor": "folder_monitor",
    "EmailTrigger": "email_trigger",
}

__all__ = [
    "ScheduleTrigger",
    "FolderMonitor",
    "EmailTrigger",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import trigger components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
