from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from loguru import logger

from agentcore.services.base import Service


# ---------------------------------------------------------------------------
# Connector catalogue helpers (async)
# ---------------------------------------------------------------------------

async def _get_storage_connector_config(connector_id: str) -> dict | None:
    """Fetch and decrypt provider_config for a storage connector from the DB."""
    from uuid import UUID as _UUID
    try:
        from agentcore.services.deps import get_db_service
        from agentcore.services.database.models.connector_catalogue.model import ConnectorCatalogue
        from agentcore.api.connector_catalogue import _decrypt_provider_config

        db_service = get_db_service()
        async with db_service.with_session() as session:
            row = await session.get(ConnectorCatalogue, _UUID(str(connector_id)))
            if row is None:
                logger.warning(f"TriggerService: connector {connector_id} not found")
                return None

            raw = row.provider_config or {}
            try:
                config = _decrypt_provider_config(row.provider, raw)
            except Exception as e:
                logger.error(f"TriggerService: failed to decrypt provider_config: {e}")
                config = raw

            return {"provider": row.provider, **config}
    except Exception as e:
        logger.error(f"TriggerService: failed to load connector config {connector_id}: {e}", exc_info=True)
        return None


class TriggerService(Service):
    """Manages non-schedule triggers: folder monitors.

    Runs background asyncio tasks that poll external sources (local folders,
    Azure Blob, SharePoint) and invoke agent flows when new data is detected.
    """

    name = "trigger_service"

    def __init__(self) -> None:
        self._monitors: dict[str, asyncio.Task] = {}
        self._seen_files: dict[str, set[str]] = {}  # trigger_id -> set of seen file keys
        self._started = False

    def start(self) -> None:
        """Start the trigger service."""
        self._started = True
        logger.info("TriggerService started")
        self.set_ready()

    async def teardown(self) -> None:
        """Cancel all monitor tasks and clean up."""
        for task_id, task in self._monitors.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled monitor task {task_id}")
        self._monitors.clear()
        self._seen_files.clear()
        self._started = False
        logger.info("TriggerService shut down")

    async def load_active_monitors(self) -> None:
        """Load all active folder/email monitors from the database."""
        from agentcore.services.deps import get_db_service

        try:
            db_service = get_db_service()
            async with db_service.with_session() as session:
                from agentcore.services.database.models.trigger_config.crud import (
                    get_active_triggers_by_type,
                )
                from agentcore.services.database.models.trigger_config.model import TriggerTypeEnum

                # Load folder monitors
                folder_triggers = await get_active_triggers_by_type(session, TriggerTypeEnum.FOLDER_MONITOR)
                for trigger in folder_triggers:
                    await self.register_folder_monitor(trigger)

                logger.info(f"Loaded {len(folder_triggers)} active folder monitors")
        except Exception as e:
            logger.warning(f"Failed to load active monitors (table may not exist yet): {e}")

    async def register_folder_monitor(self, trigger_record) -> None:
        """Register a folder monitor from a TriggerConfigTable record."""
        task_id = str(trigger_record.id)
        if task_id in self._monitors:
            await self.unregister(trigger_record.id)

        config = trigger_record.trigger_config or {}
        self._seen_files[task_id] = set()

        task = asyncio.create_task(
            self._folder_monitor_loop(
                trigger_config_id=trigger_record.id,
                agent_id=trigger_record.agent_id,
                config=config,
                environment=trigger_record.environment,
                version=trigger_record.version,
            ),
            name=f"folder_monitor_{task_id}",
        )
        self._monitors[task_id] = task
        logger.info(f"Registered folder monitor {task_id} for agent {trigger_record.agent_id}")

    async def unregister(self, trigger_config_id: UUID) -> bool:
        """Unregister and cancel a monitor task."""
        task_id = str(trigger_config_id)
        task = self._monitors.pop(task_id, None)
        self._seen_files.pop(task_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(f"Unregistered monitor {task_id}")
            return True
        return False

    # ── Folder Monitor Loop ────────────────────────────────────────────────

    async def _folder_monitor_loop(
        self,
        trigger_config_id: UUID,
        agent_id: UUID,
        config: dict,
        environment: str,
        version: str | None,
    ) -> None:
        """Poll a folder for new/changed files and trigger the agent flow."""
        storage_type = config.get("storage_type", "Local")
        poll_interval = config.get("poll_interval_seconds", 30)
        batch_size = config.get("batch_size", 10)
        trigger_on = config.get("trigger_on", "New Files")
        file_types = config.get("file_types", [])
        task_id = str(trigger_config_id)

        logger.info(
            f"Folder monitor started: storage={storage_type}, "
            f"poll={poll_interval}s, batch={batch_size}"
        )

        while True:
            try:
                await asyncio.sleep(poll_interval)

                new_files = []
                if storage_type == "Local":
                    new_files = await self._scan_local_folder(task_id, config, file_types, trigger_on)
                elif storage_type == "Azure Blob Storage":
                    new_files = await self._scan_azure_blob(task_id, config, file_types, trigger_on)
                elif storage_type == "SharePoint":
                    new_files = await self._scan_sharepoint(task_id, config, file_types, trigger_on)

                if not new_files:
                    continue

                # Apply batch size limit
                if batch_size > 0:
                    new_files = new_files[:batch_size]

                logger.info(f"Folder monitor {task_id}: found {len(new_files)} new files")

                # Trigger the agent flow with file list
                await self._execute_trigger(
                    trigger_config_id=trigger_config_id,
                    agent_id=agent_id,
                    payload={"files": new_files, "storage_type": storage_type},
                    environment=environment,
                    version=version,
                )

                # Move processed files if configured
                if config.get("move_processed", True) and storage_type == "Local":
                    await self._move_processed_files(config, new_files)

            except asyncio.CancelledError:
                logger.debug(f"Folder monitor {task_id} cancelled")
                break
            except Exception:
                logger.exception(f"Error in folder monitor {task_id}")
                await asyncio.sleep(poll_interval)

    async def _scan_local_folder(
        self, task_id: str, config: dict, file_types: list[str], trigger_on: str,
    ) -> list[dict]:
        """Scan a local folder for new/modified files."""
        folder_path = config.get("folder_path", ".")
        if not os.path.isdir(folder_path):
            logger.warning(f"Folder monitor {task_id}: path '{folder_path}' does not exist")
            return []

        seen = self._seen_files.get(task_id, set())
        new_files = []

        for entry in os.scandir(folder_path):
            if not entry.is_file():
                continue

            # Filter by file type
            if file_types:
                ext = Path(entry.name).suffix.lstrip(".")
                if ext not in file_types:
                    continue

            file_key = f"{entry.name}:{entry.stat().st_mtime}"

            if trigger_on in ("New Files", "Both") and entry.name not in {
                k.split(":")[0] for k in seen
            }:
                new_files.append({
                    "name": entry.name,
                    "path": entry.path,
                    "size": entry.stat().st_size,
                    "modified": datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
                seen.add(file_key)
            elif trigger_on in ("Modified Files", "Both") and file_key not in seen:
                new_files.append({
                    "name": entry.name,
                    "path": entry.path,
                    "size": entry.stat().st_size,
                    "modified": datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
                seen.add(file_key)

        self._seen_files[task_id] = seen
        return new_files

    async def _scan_azure_blob(
        self, task_id: str, config: dict, file_types: list[str], trigger_on: str,
    ) -> list[dict]:
        """Scan an Azure Blob container for new/modified blobs.

        Credentials are resolved from the connector_catalogue via `connector_id`
        stored in the trigger_config JSON.
        """
        try:
            from azure.storage.blob.aio import BlobServiceClient
        except ImportError:
            logger.error("azure-storage-blob not installed. Install with: pip install azure-storage-blob")
            return []

        # Resolve credentials from connector catalogue
        connector_id = config.get("connector_id")
        if connector_id:
            connector_cfg = await _get_storage_connector_config(str(connector_id))
            if not connector_cfg:
                logger.error(f"TriggerService: could not load Azure connector {connector_id}")
                return []
            connection_string = connector_cfg.get("connection_string", "")
            container_name = connector_cfg.get("container_name", "")
            prefix = connector_cfg.get("blob_prefix", config.get("azure_prefix", ""))
        else:
            # Fallback: legacy inline credentials (deprecated)
            connection_string = config.get("azure_connection_string", "")
            container_name = config.get("azure_container", "")
            prefix = config.get("azure_prefix", "")

        if not connection_string or not container_name:
            logger.warning(f"TriggerService: Azure Blob trigger {task_id} missing connection_string or container_name")
            return []

        seen = self._seen_files.get(task_id, set())
        new_files = []

        async with BlobServiceClient.from_connection_string(connection_string) as client:
            container = client.get_container_client(container_name)
            async for blob in container.list_blobs(name_starts_with=prefix or None):
                if file_types:
                    ext = Path(blob.name).suffix.lstrip(".")
                    if ext not in file_types:
                        continue

                blob_key = f"{blob.name}:{blob.last_modified.isoformat() if blob.last_modified else ''}"

                if blob_key not in seen:
                    new_files.append({
                        "name": blob.name,
                        "path": f"azure://{container_name}/{blob.name}",
                        "size": blob.size,
                        "modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    })
                    seen.add(blob_key)

        self._seen_files[task_id] = seen
        return new_files

    async def _scan_sharepoint(
        self, task_id: str, config: dict, file_types: list[str], trigger_on: str,
    ) -> list[dict]:
        """Scan a SharePoint document library for new/modified files.

        Credentials are resolved from the connector_catalogue via `connector_id`
        stored in the trigger_config JSON.
        """
        try:
            from office365.runtime.auth.client_credential import ClientCredential
            from office365.sharepoint.client_context import ClientContext
        except ImportError:
            logger.error(
                "Office365-REST-Python-Client not installed. "
                "Install with: pip install Office365-REST-Python-Client"
            )
            return []

        # Resolve credentials from connector catalogue
        connector_id = config.get("connector_id")
        if connector_id:
            connector_cfg = await _get_storage_connector_config(str(connector_id))
            if not connector_cfg:
                logger.error(f"TriggerService: could not load SharePoint connector {connector_id}")
                return []
            site_url = connector_cfg.get("site_url", "")
            client_id = connector_cfg.get("client_id", "")
            client_secret = connector_cfg.get("client_secret", "")
            library = connector_cfg.get("library", "Shared Documents")
            folder_path = connector_cfg.get("folder", config.get("sharepoint_folder", ""))
        else:
            # Fallback: legacy inline credentials (deprecated)
            site_url = config.get("sharepoint_site_url", "")
            client_id = config.get("sharepoint_client_id", "")
            client_secret = config.get("sharepoint_client_secret", "")
            library = config.get("sharepoint_library", "Shared Documents")
            folder_path = config.get("sharepoint_folder", "")

        if not site_url or not client_id or not client_secret:
            logger.warning(f"TriggerService: SharePoint trigger {task_id} missing site_url, client_id, or client_secret")
            return []

        seen = self._seen_files.get(task_id, set())
        new_files = []

        try:
            credentials = ClientCredential(client_id, client_secret)
            ctx = ClientContext(site_url).with_credentials(credentials)

            target_folder = ctx.web.get_folder_by_server_relative_url(
                f"{library}/{folder_path}" if folder_path else library
            )
            files = target_folder.files
            ctx.load(files)
            await asyncio.to_thread(ctx.execute_query)

            for sp_file in files:
                if file_types:
                    ext = Path(sp_file.name).suffix.lstrip(".")
                    if ext not in file_types:
                        continue

                modified = sp_file.time_last_modified if hasattr(sp_file, "time_last_modified") else ""
                file_key = f"{sp_file.name}:{modified}"

                if file_key not in seen:
                    new_files.append({
                        "name": sp_file.name,
                        "path": sp_file.serverRelativeUrl,
                        "size": sp_file.length if hasattr(sp_file, "length") else 0,
                        "modified": str(modified),
                    })
                    seen.add(file_key)

        except Exception:
            logger.exception(f"Error scanning SharePoint for trigger {task_id}")

        self._seen_files[task_id] = seen
        return new_files

    async def _move_processed_files(self, config: dict, files: list[dict]) -> None:
        """Move processed local files to a 'processed' subfolder."""
        folder_path = config.get("folder_path", ".")
        processed_dir = os.path.join(folder_path, "processed")
        os.makedirs(processed_dir, exist_ok=True)

        for file_info in files:
            src = file_info.get("path", "")
            if src and os.path.isfile(src):
                dst = os.path.join(processed_dir, os.path.basename(src))
                try:
                    await asyncio.to_thread(os.rename, src, dst)
                except OSError:
                    logger.warning(f"Could not move {src} to {dst}")

    # ── Common Execution ───────────────────────────────────────────────────

    async def _execute_trigger(
        self,
        trigger_config_id: UUID,
        agent_id: UUID,
        payload: dict,
        environment: str,
        version: str | None,
    ) -> None:
        """Execute the agent flow with the trigger payload."""
        from agentcore.services.deps import get_db_service

        start_time = time.perf_counter()

        try:
            db_service = get_db_service()
            async with db_service.with_session() as session:
                from agentcore.services.database.models.trigger_config.crud import (
                    log_trigger_execution,
                    update_trigger_last_run,
                )
                from agentcore.services.database.models.trigger_config.model import (
                    TriggerExecutionStatusEnum,
                )

                await log_trigger_execution(
                    session,
                    trigger_config_id=trigger_config_id,
                    agent_id=agent_id,
                    status=TriggerExecutionStatusEnum.STARTED,
                    payload=payload,
                )
                await update_trigger_last_run(session, trigger_config_id)

            # Run the agent flow
            await self._run_agent_flow(agent_id, environment, version, trigger_config_id, payload)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            async with db_service.with_session() as session:
                await log_trigger_execution(
                    session,
                    trigger_config_id=trigger_config_id,
                    agent_id=agent_id,
                    status=TriggerExecutionStatusEnum.SUCCESS,
                    execution_duration_ms=elapsed_ms,
                )

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Trigger execution failed: {exc}")

            try:
                async with db_service.with_session() as session:
                    from agentcore.services.database.models.trigger_config.crud import log_trigger_execution
                    from agentcore.services.database.models.trigger_config.model import TriggerExecutionStatusEnum

                    await log_trigger_execution(
                        session,
                        trigger_config_id=trigger_config_id,
                        agent_id=agent_id,
                        status=TriggerExecutionStatusEnum.ERROR,
                        error_message=str(exc),
                        execution_duration_ms=elapsed_ms,
                    )
            except Exception:
                logger.exception("Failed to log trigger execution error")

    async def _run_agent_flow(
        self,
        agent_id: UUID,
        environment: str,
        version: str | None,
        trigger_config_id: UUID,
        payload: dict,
    ) -> None:
        """Invoke the agent flow using the existing execution pipeline."""
        import json

        from agentcore.services.deps import get_db_service

        db_service = get_db_service()
        async with db_service.with_session() as session:
            from sqlmodel import select

            from agentcore.services.database.models.agent.model import Agent

            stmt = select(Agent).where(Agent.id == agent_id)
            result = await session.exec(stmt)
            agent = result.first()

            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

        from agentcore.api.endpoints import _resolve_agent_data_for_env, simple_run_agent_task
        from agentcore.api.schemas import SimplifiedAPIRequest

        agent.data, prod_deployment, uat_deployment = await _resolve_agent_data_for_env(
            agent_id=agent.id,
            env=environment,
            version=version or "v1",
        )

        input_request = SimplifiedAPIRequest(
            input_value=json.dumps(payload),
            input_type="chat",
            output_type="chat",
            tweaks={},
            session_id=None,
        )

        await simple_run_agent_task(
            agent=agent,
            input_request=input_request,
            api_key_user=None,
            prod_deployment=prod_deployment,
            uat_deployment=uat_deployment,
        )
