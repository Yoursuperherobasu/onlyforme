"""Folder Monitor trigger component.

Monitors a folder for new or changed files. Supports local filesystem,
Azure Blob Storage, and SharePoint.

For cloud storage (Azure Blob, SharePoint), credentials are NOT stored inline.
Instead, a connector is selected from the Connectors Catalogue (configured
on the Connectors page). This keeps secrets centralised and auditable.
"""

import asyncio
import concurrent.futures
from datetime import datetime, timezone

from loguru import logger

from agentcore.base.data.utils import TEXT_FILE_TYPES
from agentcore.custom.custom_node.node import Node
from agentcore.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultiselectInput,
    Output,
)
from agentcore.schema.data import Data
from agentcore.schema.dataframe import DataFrame
from agentcore.schema.message import Message
from agentcore.utils.constants import MESSAGE_SENDER_USER


# ---------------------------------------------------------------------------
# Async helper (same pattern as database_connector.py)
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from a synchronous context."""
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Catalogue helpers
# ---------------------------------------------------------------------------

_STORAGE_TYPE_TO_PROVIDER = {
    "Azure Blob Storage": "azure_blob",
    "SharePoint": "sharepoint",
}


def _fetch_storage_connectors(provider_key: str) -> list[str]:
    """Return connector dropdown options for a given provider.

    Format: "name | provider | target_info | uuid"
    """
    try:
        from agentcore.services.deps import get_db_service

        db_service = get_db_service()

        async def _query():
            from sqlalchemy import select
            from agentcore.services.database.models.connector_catalogue.model import ConnectorCatalogue

            async with db_service.with_session() as session:
                stmt = (
                    select(ConnectorCatalogue)
                    .where(ConnectorCatalogue.provider == provider_key)
                    .order_by(ConnectorCatalogue.name)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                options = []
                for r in rows:
                    cfg = r.provider_config or {}
                    if provider_key == "azure_blob":
                        target = cfg.get("container_name", "—")
                    else:  # sharepoint
                        target = cfg.get("site_url", "—")
                    options.append(f"{r.name} | {r.provider} | {target} | {r.id}")
                return options

        return _run_async(_query())
    except Exception as e:
        logger.warning(f"Could not fetch storage connectors from catalogue: {e}")
        return []


def _get_storage_connector_config(connector_id: str) -> dict | None:
    """Fetch and decrypt a storage connector's provider_config from the DB."""
    import threading
    from uuid import UUID

    _engine_lock = threading.Lock()

    try:
        from agentcore.services.deps import get_db_service

        db_service = get_db_service()

        async def _query():
            from sqlalchemy import select
            from agentcore.services.database.models.connector_catalogue.model import ConnectorCatalogue

            async with db_service.with_session() as session:
                row = await session.get(ConnectorCatalogue, UUID(connector_id))
                if row is None:
                    logger.warning(f"Storage connector {connector_id} not found")
                    return None

                raw_config = row.provider_config or {}
                try:
                    from agentcore.api.connector_catalogue import _decrypt_provider_config
                    config = _decrypt_provider_config(row.provider, raw_config)
                except Exception as e:
                    logger.error(f"Failed to decrypt provider_config: {e}")
                    config = raw_config

                return {"provider": row.provider, **config}

        return _run_async(_query())
    except Exception as e:
        logger.error(f"Failed to fetch storage connector config for {connector_id}: {e}", exc_info=True)
        return None


def _parse_connector_id(connector_value: str) -> str | None:
    """Extract UUID from a connector dropdown option string.

    Format: "name | provider | target | uuid"
    """
    if not connector_value:
        return None
    parts = connector_value.split("|")
    if len(parts) >= 4:
        return parts[-1].strip()
    # Maybe the value IS a plain UUID
    return connector_value.strip()


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

class FolderMonitor(Node):
    display_name = "Folder Monitor"
    description = (
        "Monitors a folder for new or changed files. "
        "Supports local filesystem, Azure Blob Storage, and SharePoint. "
        "Cloud storage credentials are managed via the Connectors page."
    )
    icon = "FolderSearch"
    name = "FolderMonitor"

    inputs = [
        DropdownInput(
            name="storage_type",
            display_name="Storage Type",
            options=["Local", "Azure Blob Storage", "SharePoint"],
            value="Local",
            info="Select the storage backend to monitor.",
            real_time_refresh=True,
        ),
        # --- Local mode ---
        MessageTextInput(
            name="folder_path",
            display_name="Folder Path",
            info="Local directory path to monitor for new/changed files.",
            value=".",
        ),
        # --- Cloud storage: connector selector ---
        DropdownInput(
            name="connector",
            display_name="Connector",
            info=(
                "Select a connector configured on the Connectors page. "
                "The connector holds the credentials for Azure Blob or SharePoint."
            ),
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
        ),
        # --- Common ---
        IntInput(
            name="poll_interval_seconds",
            display_name="Poll Interval (seconds)",
            value=30,
            info="How often to check for new files (used when deployed).",
        ),
        MultiselectInput(
            name="file_types",
            display_name="File Types",
            options=TEXT_FILE_TYPES,
            value=[],
            info="File types to monitor. Leave empty for all supported types.",
        ),
        DropdownInput(
            name="trigger_on",
            display_name="Trigger On",
            options=["New Files", "Modified Files", "Both"],
            value="New Files",
            info="When to trigger: on new files only, modified files only, or both.",
        ),
        BoolInput(
            name="move_processed",
            display_name="Move Processed Files",
            value=True,
            info="Move processed files to a 'processed' subfolder after processing (Local only).",
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            value=10,
            info="Maximum files to process per trigger. 0 = unlimited.",
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID for this trigger. If empty, a new session is created per execution.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Files",
            name="files",
            method="files_output",
        ),
        Output(
            display_name="Trigger Info",
            name="trigger_info",
            method="info_output",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Show/hide inputs based on storage_type and refresh connector options."""
        from agentcore.utils.component_utils import set_current_fields, set_field_display

        storage_type = build_config["storage_type"]["value"]

        mode_config = {
            "Local": ["folder_path"],
            "Azure Blob Storage": ["connector"],
            "SharePoint": ["connector"],
        }
        default_keys = [
            "code",
            "_type",
            "storage_type",
            "poll_interval_seconds",
            "file_types",
            "trigger_on",
            "move_processed",
            "batch_size",
            "session_id",
        ]

        # Refresh connector options when storage type changes or refresh is triggered
        if storage_type in ("Azure Blob Storage", "SharePoint"):
            provider_key = _STORAGE_TYPE_TO_PROVIDER[storage_type]
            options = _fetch_storage_connectors(provider_key)
            build_config["connector"]["options"] = options
            if options and not build_config["connector"].get("value"):
                build_config["connector"]["value"] = options[0]

        return set_current_fields(
            build_config=build_config,
            action_fields=mode_config,
            selected_action=storage_type,
            default_fields=default_keys,
            func=set_field_display,
        )

    # ── Local ──────────────────────────────────────────────────────────────

    def _scan_local_folder(self) -> list[Data]:
        """Scan local folder for files."""
        from agentcore.base.data.utils import parse_text_file_to_data, retrieve_file_paths

        resolved_path = self.resolve_path(self.folder_path)
        types = self.file_types if self.file_types else TEXT_FILE_TYPES

        file_paths = retrieve_file_paths(
            resolved_path, load_hidden=False, recursive=True, depth=0, types=types
        )

        batch_size = self.batch_size
        if batch_size and batch_size > 0:
            file_paths = file_paths[:batch_size]

        loaded_data = []
        for file_path in file_paths:
            try:
                from agentcore.base.data.utils import parse_text_file_to_data
                data = parse_text_file_to_data(file_path, silent_errors=True)
                if data is not None and isinstance(data, Data):
                    loaded_data.append(data)
            except Exception as e:
                logger.warning(f"Failed to parse file {file_path}: {e}")

        return loaded_data

    # ── Azure Blob ─────────────────────────────────────────────────────────

    async def _scan_azure_blob(self) -> list[Data]:
        """Scan Azure Blob Storage for files using credentials from the connector catalogue."""

        connector_id = _parse_connector_id(self.connector)
        if not connector_id:
            logger.warning("FolderMonitor: no connector selected for Azure Blob Storage")
            return []

        config = _get_storage_connector_config(connector_id)
        if not config:
            logger.error(f"FolderMonitor: could not load connector config for {connector_id}")
            return []

        connection_string = config.get("connection_string", "")
        container_name = config.get("container_name", "")
        prefix = config.get("blob_prefix", "")

        if not connection_string or not container_name:
            logger.error("FolderMonitor: Azure connector is missing connection_string or container_name")
            return []

        def _do_scan():
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                raise ImportError(
                    "azure-storage-blob is required. Install with: pip install azure-storage-blob"
                )

            types = self.file_types if self.file_types else TEXT_FILE_TYPES
            batch_size = self.batch_size

            blob_service = BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service.get_container_client(container_name)
            blobs = list(container_client.list_blobs(name_starts_with=prefix if prefix else None))

            filtered = [
                b for b in blobs
                if not types or ("." + b.name.rsplit(".", 1)[-1] if "." in b.name else "") in types
            ]
            if batch_size and batch_size > 0:
                filtered = filtered[:batch_size]

            data_list = []
            for blob in filtered:
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    content = blob_client.download_blob().readall().decode("utf-8", errors="replace")
                    data_list.append(
                        Data(
                            data={
                                "text": content,
                                "file_path": blob.name,
                                "source": f"azure://{container_name}/{blob.name}",
                                "last_modified": (
                                    blob.last_modified.isoformat() if blob.last_modified else ""
                                ),
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read blob {blob.name}: {e}")

            return data_list

        return await asyncio.to_thread(_do_scan)

    # ── SharePoint ─────────────────────────────────────────────────────────

    async def _scan_sharepoint(self) -> list[Data]:
        """Scan SharePoint document library for files using credentials from the connector catalogue."""

        connector_id = _parse_connector_id(self.connector)
        if not connector_id:
            logger.warning("FolderMonitor: no connector selected for SharePoint")
            return []

        config = _get_storage_connector_config(connector_id)
        if not config:
            logger.error(f"FolderMonitor: could not load connector config for {connector_id}")
            return []

        site_url = config.get("site_url", "")
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        library = config.get("library", "Shared Documents")
        folder = config.get("folder", "")

        if not site_url or not client_id or not client_secret:
            logger.error("FolderMonitor: SharePoint connector is missing site_url, client_id, or client_secret")
            return []

        def _do_scan():
            try:
                from office365.runtime.auth.client_credential import ClientCredential
                from office365.sharepoint.client_context import ClientContext
            except ImportError:
                raise ImportError(
                    "Office365-REST-Python-Client is required. "
                    "Install with: pip install Office365-REST-Python-Client"
                )

            types = self.file_types if self.file_types else TEXT_FILE_TYPES
            batch_size = self.batch_size

            credentials = ClientCredential(client_id, client_secret)
            ctx = ClientContext(site_url).with_credentials(credentials)

            folder_url = f"{library}/{folder}".rstrip("/")
            target_folder = ctx.web.get_folder_by_server_relative_url(folder_url)
            files = target_folder.files
            ctx.load(files)
            ctx.execute_query()

            filtered = [
                f for f in files
                if not types or ("." + f.name.rsplit(".", 1)[-1] if "." in f.name else "") in types
            ]
            if batch_size and batch_size > 0:
                filtered = filtered[:batch_size]

            data_list = []
            for f in filtered:
                try:
                    content_bytes = bytearray()
                    f.download(content_bytes).execute_query()
                    content = bytes(content_bytes).decode("utf-8", errors="replace")
                    data_list.append(
                        Data(
                            data={
                                "text": content,
                                "file_path": f.name,
                                "source": f"sharepoint://{site_url}/{folder_url}/{f.name}",
                                "last_modified": (
                                    str(f.time_last_modified)
                                    if hasattr(f, "time_last_modified")
                                    else ""
                                ),
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read SharePoint file {f.name}: {e}")

            return data_list

        return await asyncio.to_thread(_do_scan)

    # ── Outputs ────────────────────────────────────────────────────────────

    async def files_output(self) -> DataFrame:
        """Load files from the configured storage backend and return as DataFrame."""
        storage_type = self.storage_type

        if storage_type == "Local":
            data_list = self._scan_local_folder()
        elif storage_type == "Azure Blob Storage":
            data_list = await self._scan_azure_blob()
        elif storage_type == "SharePoint":
            data_list = await self._scan_sharepoint()
        else:
            data_list = []

        self.status = data_list
        return DataFrame(data_list)

    async def info_output(self) -> Message:
        """Return trigger metadata as a Message."""
        now = datetime.now(timezone.utc)
        storage_type = self.storage_type

        metadata: dict = {
            "trigger_type": "folder_monitor",
            "storage_type": storage_type,
            "triggered_at": now.isoformat(),
            "trigger_on": self.trigger_on,
            "batch_size": self.batch_size,
        }

        if storage_type == "Local":
            metadata["folder_path"] = self.folder_path
        else:
            # Cloud connector: include connector reference (no raw credentials)
            metadata["connector"] = self.connector

        message = await Message.create(
            text=f"Folder monitor triggered ({storage_type})",
            sender=MESSAGE_SENDER_USER,
            sender_name="FolderMonitor",
            session_id=self.session_id if hasattr(self, "session_id") and self.session_id else "",
            properties={"trigger_metadata": metadata},
        )

        self.status = message
        return message
