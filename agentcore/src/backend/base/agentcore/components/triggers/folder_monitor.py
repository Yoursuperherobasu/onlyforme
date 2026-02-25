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
    SecretStrInput,
)
from agentcore.schema.data import Data
from agentcore.schema.dataframe import DataFrame
from agentcore.schema.message import Message
from agentcore.utils.constants import MESSAGE_SENDER_USER


class FolderMonitor(Node):
    display_name = "Folder Monitor"
    description = "Monitors a folder for new or changed files. Supports local filesystem, Azure Blob Storage, and SharePoint."
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
        # --- Azure Blob mode ---
        SecretStrInput(
            name="azure_connection_string",
            display_name="Azure Connection String",
            info="Connection string for Azure Blob Storage.",
        ),
        MessageTextInput(
            name="azure_container",
            display_name="Container Name",
            info="Azure Blob Storage container name.",
        ),
        MessageTextInput(
            name="azure_prefix",
            display_name="Blob Prefix (folder)",
            info="Optional prefix to filter blobs (e.g., 'inbox/'). Leave empty for root.",
            value="",
        ),
        # --- SharePoint mode ---
        MessageTextInput(
            name="sharepoint_site_url",
            display_name="SharePoint Site URL",
            info="Full URL to the SharePoint site (e.g., 'https://tenant.sharepoint.com/sites/MySite').",
        ),
        MessageTextInput(
            name="sharepoint_library",
            display_name="Document Library",
            value="Shared Documents",
            info="Name of the SharePoint document library.",
        ),
        MessageTextInput(
            name="sharepoint_folder",
            display_name="Folder Path",
            info="Relative folder path within the library. Leave empty for root.",
            value="",
        ),
        SecretStrInput(
            name="sharepoint_client_id",
            display_name="App Client ID",
            info="Azure AD App Registration client ID for SharePoint access.",
        ),
        SecretStrInput(
            name="sharepoint_client_secret",
            display_name="App Client Secret",
            info="Azure AD App Registration client secret.",
        ),
        MessageTextInput(
            name="sharepoint_tenant_id",
            display_name="Tenant ID",
            info="Azure AD tenant ID.",
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
            info="Move processed files to a 'processed' subfolder after processing.",
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
        """Show/hide inputs based on storage_type selection."""
        from agentcore.utils.component_utils import set_current_fields, set_field_display

        mode_config = {
            "Local": ["folder_path"],
            "Azure Blob Storage": [
                "azure_connection_string",
                "azure_container",
                "azure_prefix",
            ],
            "SharePoint": [
                "sharepoint_site_url",
                "sharepoint_library",
                "sharepoint_folder",
                "sharepoint_client_id",
                "sharepoint_client_secret",
                "sharepoint_tenant_id",
            ],
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
        return set_current_fields(
            build_config=build_config,
            action_fields=mode_config,
            selected_action=build_config["storage_type"]["value"],
            default_fields=default_keys,
            func=set_field_display,
        )

    def _scan_local_folder(self) -> list[Data]:
        """Scan local folder for files."""
        from agentcore.base.data.utils import parse_text_file_to_data, retrieve_file_paths

        resolved_path = self.resolve_path(self.folder_path)
        types = self.file_types if self.file_types else TEXT_FILE_TYPES

        file_paths = retrieve_file_paths(resolved_path, load_hidden=False, recursive=True, depth=0, types=types)

        batch_size = self.batch_size
        if batch_size and batch_size > 0:
            file_paths = file_paths[:batch_size]

        loaded_data = []
        for file_path in file_paths:
            try:
                data = parse_text_file_to_data(file_path, silent_errors=True)
                if data is not None and isinstance(data, Data):
                    loaded_data.append(data)
            except Exception as e:
                logger.warning(f"Failed to parse file {file_path}: {e}")

        return loaded_data

    async def _scan_azure_blob(self) -> list[Data]:
        """Scan Azure Blob Storage for files."""
        import asyncio

        def _do_scan():
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                msg = "azure-storage-blob is required for Azure Blob Storage monitoring. Install with: pip install azure-storage-blob"
                raise ImportError(msg)

            connection_string = self.azure_connection_string
            container_name = self.azure_container
            prefix = self.azure_prefix or ""
            types = self.file_types if self.file_types else TEXT_FILE_TYPES
            batch_size = self.batch_size

            blob_service = BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service.get_container_client(container_name)

            blobs = list(container_client.list_blobs(name_starts_with=prefix if prefix else None))

            # Filter by file type
            filtered = []
            for blob in blobs:
                ext = "." + blob.name.rsplit(".", 1)[-1] if "." in blob.name else ""
                if ext in types:
                    filtered.append(blob)

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
                                "last_modified": blob.last_modified.isoformat() if blob.last_modified else "",
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read blob {blob.name}: {e}")

            return data_list

        return await asyncio.to_thread(_do_scan)

    async def _scan_sharepoint(self) -> list[Data]:
        """Scan SharePoint document library for files."""
        import asyncio

        def _do_scan():
            try:
                from office365.runtime.auth.client_credential import ClientCredential
                from office365.sharepoint.client_context import ClientContext
            except ImportError:
                msg = "Office365-REST-Python-Client is required for SharePoint monitoring. Install with: pip install Office365-REST-Python-Client"
                raise ImportError(msg)

            site_url = self.sharepoint_site_url
            client_id = self.sharepoint_client_id
            client_secret = self.sharepoint_client_secret
            library = self.sharepoint_library
            folder = self.sharepoint_folder or ""
            types = self.file_types if self.file_types else TEXT_FILE_TYPES
            batch_size = self.batch_size

            credentials = ClientCredential(client_id, client_secret)
            ctx = ClientContext(site_url).with_credentials(credentials)

            # Build folder path
            folder_url = f"{library}/{folder}".rstrip("/")
            target_folder = ctx.web.get_folder_by_server_relative_url(folder_url)
            files = target_folder.files
            ctx.load(files)
            ctx.execute_query()

            # Filter by file type
            filtered = []
            for f in files:
                ext = "." + f.name.rsplit(".", 1)[-1] if "." in f.name else ""
                if ext in types:
                    filtered.append(f)

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
                                "last_modified": str(f.time_last_modified) if hasattr(f, "time_last_modified") else "",
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read SharePoint file {f.name}: {e}")

            return data_list

        return await asyncio.to_thread(_do_scan)

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

        metadata = {
            "trigger_type": "folder_monitor",
            "storage_type": storage_type,
            "triggered_at": now.isoformat(),
            "trigger_on": self.trigger_on,
            "batch_size": self.batch_size,
        }

        if storage_type == "Local":
            metadata["folder_path"] = self.folder_path
        elif storage_type == "Azure Blob Storage":
            metadata["container"] = self.azure_container
            metadata["prefix"] = self.azure_prefix
        elif storage_type == "SharePoint":
            metadata["site_url"] = self.sharepoint_site_url
            metadata["library"] = self.sharepoint_library
            metadata["folder"] = self.sharepoint_folder

        message = await Message.create(
            text=f"Folder monitor triggered ({storage_type})",
            sender=MESSAGE_SENDER_USER,
            sender_name="FolderMonitor",
            session_id=self.session_id if hasattr(self, "session_id") and self.session_id else "",
            properties={"trigger_metadata": metadata},
        )

        self.status = message
        return message
