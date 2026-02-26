"""Backward compatibility shim.

The FolderMonitor component has been renamed to FileTrigger and moved to
``agentcore.components.tools.file_trigger``.  This shim keeps the old
import path working so existing agent snapshots that reference
``agentcore.components.triggers.FolderMonitor`` continue to resolve.
"""

from __future__ import annotations

from agentcore.components.tools.file_trigger import FileTrigger as FolderMonitor  # noqa: F401

__all__ = ["FolderMonitor"]
