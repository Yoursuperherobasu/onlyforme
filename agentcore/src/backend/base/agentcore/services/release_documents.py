from __future__ import annotations

import html
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import anyio
from aiofile import async_open
from loguru import logger

from agentcore.services.settings.service import SettingsService

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OFFICE_VIEWER_BASE_URL = "https://view.officeapps.live.com/op/embed.aspx?src="


def sanitize_release_document_name(file_name: str) -> str:
    cleaned = Path(file_name or "release-notes.docx").name.strip()
    if not cleaned:
        cleaned = "release-notes.docx"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", cleaned)
    return cleaned or "release-notes.docx"


def build_release_document_path(release_id: UUID | str, file_name: str) -> str:
    return f"releases/{release_id}/{sanitize_release_document_name(file_name)}"


def _get_release_documents_container(settings_service: SettingsService) -> str:
    configured = str(
        getattr(settings_service.settings, "azure_release_documents_container_name", "") or ""
    ).strip()
    if not configured:
        raise ValueError(
            "AZURE_RELEASE_DOCUMENTS_CONTAINER_NAME is required for release document storage."
        )
    return configured


async def save_release_document(
    *,
    settings_service: SettingsService,
    release_id: UUID | str,
    file_name: str,
    content: bytes,
) -> str:
    storage_type = str(getattr(settings_service.settings, "storage_type", "local") or "local").strip().lower()
    blob_path = build_release_document_path(release_id, file_name)

    if storage_type == "azure":
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip().strip("'\"")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required when STORAGE_TYPE=azure.")

        from azure.storage.blob.aio import BlobServiceClient

        container_name = _get_release_documents_container(settings_service)
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        try:
            try:
                await container_client.get_container_properties()
            except Exception:
                await container_client.create_container()
                logger.info(f"Created Azure blob container: {container_name}")
            await container_client.upload_blob(name=blob_path, data=content, overwrite=True)
        finally:
            await blob_service_client.close()
        return blob_path

    base_dir = anyio.Path(settings_service.settings.config_dir) / "release_documents"
    file_path = base_dir / blob_path
    await file_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_open(str(file_path), "wb") as file_handle:
        await file_handle.write(content)
    return blob_path


async def get_release_document(
    *,
    settings_service: SettingsService,
    storage_path: str,
) -> bytes:
    storage_type = str(getattr(settings_service.settings, "storage_type", "local") or "local").strip().lower()

    if storage_type == "azure":
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip().strip("'\"")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required when STORAGE_TYPE=azure.")

        from azure.storage.blob.aio import BlobServiceClient

        container_name = _get_release_documents_container(settings_service)
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(storage_path)
        try:
            stream = await blob_client.download_blob()
            return await stream.readall()
        finally:
            await blob_service_client.close()

    file_path = anyio.Path(settings_service.settings.config_dir) / "release_documents" / storage_path
    if not await file_path.exists():
        raise FileNotFoundError(storage_path)
    async with async_open(str(file_path), "rb") as file_handle:
        return await file_handle.read()


def build_release_document_office_viewer_url(
    *,
    settings_service: SettingsService,
    storage_path: str,
) -> str | None:
    storage_type = str(getattr(settings_service.settings, "storage_type", "local") or "local").strip().lower()
    if storage_type != "azure":
        return None

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip().strip("'\"")
    if not connection_string:
        return None

    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    parts = {}
    for segment in connection_string.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    account_name = parts.get("accountname")
    account_key = parts.get("accountkey")
    endpoint_suffix = parts.get("endpointsuffix", "core.windows.net")
    if not account_name or not account_key:
        return None

    container_name = _get_release_documents_container(settings_service)
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=storage_path,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    if not sas_token:
        return None

    direct_url = f"https://{account_name}.blob.{endpoint_suffix}/{container_name}/{quote(storage_path)}?{sas_token}"
    return f"{OFFICE_VIEWER_BASE_URL}{quote(direct_url, safe='')}"


def render_release_document_preview_html(document_bytes: bytes) -> str:
    from docx import Document
    from io import BytesIO

    document = Document(BytesIO(document_bytes))
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list_items() -> None:
        nonlocal list_items
        if list_items:
            blocks.append(f"<ul>{''.join(list_items)}</ul>")
            list_items = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            flush_list_items()
            continue
        style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
        escaped = html.escape(text)
        if style_name.startswith("heading 1"):
            flush_list_items()
            blocks.append(f"<h1>{escaped}</h1>")
        elif style_name.startswith("heading 2"):
            flush_list_items()
            blocks.append(f"<h2>{escaped}</h2>")
        elif style_name.startswith("heading 3"):
            flush_list_items()
            blocks.append(f"<h3>{escaped}</h3>")
        elif style_name.startswith("list"):
            list_items.append(f"<li>{escaped}</li>")
        else:
            flush_list_items()
            blocks.append(f"<p>{escaped}</p>")

    flush_list_items()

    tables_html: list[str] = []
    for table in document.tables:
        rows_html: list[str] = []
        for row in table.rows:
            cols = "".join(f"<td>{html.escape(cell.text.strip())}</td>" for cell in row.cells)
            rows_html.append(f"<tr>{cols}</tr>")
        tables_html.append(f"<table>{''.join(rows_html)}</table>")

    body = "".join(blocks + tables_html)
    if not body:
        body = "<p>No previewable content found in the uploaded release document.</p>"

    return f"""
    <div class="release-doc-preview">
      {body}
    </div>
    """
