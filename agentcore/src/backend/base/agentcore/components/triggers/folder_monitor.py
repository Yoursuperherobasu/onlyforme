"""Backward compat — component moved to agentcore.components.tools.file_trigger."""

from agentcore.components.tools.file_trigger import FileTrigger as FolderMonitor  # noqa: F401

__all__ = ["FolderMonitor"]
