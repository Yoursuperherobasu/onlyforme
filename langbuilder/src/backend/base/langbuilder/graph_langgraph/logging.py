"""Logging utilities for LangGraph - fully independent implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import pandas as pd
from loguru import logger

from langbuilder.serialization.serialization import get_max_items_length, get_max_text_length, serialize
from langbuilder.services.database.models.transactions.crud import log_transaction as crud_log_transaction
from langbuilder.services.database.models.transactions.model import TransactionBase
from langbuilder.services.database.models.vertex_builds.crud import log_vertex_build as crud_log_vertex_build
from langbuilder.services.database.models.vertex_builds.model import VertexBuildBase
from langbuilder.services.database.utils import session_getter
from langbuilder.services.deps import get_db_service, get_settings_service


def _vertex_to_primitive_dict(vertex_params: dict) -> dict:
    """Cleans the parameters of the vertex to only include primitive types."""
    params = {
        key: value for key, value in vertex_params.items() if isinstance(value, str | int | bool | float | list | dict)
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, str | int | bool | float | list | dict)]
    return params


async def log_transaction(
    flow_id: str | UUID,
    vertex_id: str,
    status: str,
    inputs: dict | None = None,
    outputs: dict | None = None,
    target_id: str | None = None,
    error: str | None = None,
) -> None:
    """Asynchronously logs a transaction record for a vertex in a flow if transaction storage is enabled.

    Args:
        flow_id: The flow ID (string or UUID)
        vertex_id: The source vertex ID
        status: Transaction status ("success" or "error")
        inputs: The vertex inputs (optional)
        outputs: The vertex outputs (optional)
        target_id: The target vertex ID (optional)
        error: Error message if status is "error" (optional)
    """
    try:
        print(f"🔍 LOG_TRANSACTION called: vertex_id={vertex_id}, flow_id={flow_id}, status={status}")
        logger.info(f"LOG_TRANSACTION called: vertex_id={vertex_id}, flow_id={flow_id}, status={status}")
        
        if not get_settings_service().settings.transactions_storage_enabled:
            print(f"⚠️ LOG_TRANSACTION: Storage disabled by settings")
            logger.warning("Transaction storage is disabled in settings")
            return
        
        # Convert flow_id to UUID if needed
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)
        
        # Serialize inputs and outputs
        serialized_inputs = serialize(inputs, max_length=get_max_text_length(), max_items=get_max_items_length()) if inputs else None
        serialized_outputs = serialize(outputs, max_length=get_max_text_length(), max_items=get_max_items_length()) if outputs else None
        
        transaction = TransactionBase(
            vertex_id=vertex_id,
            target_id=target_id,
            inputs=serialized_inputs,
            outputs=serialized_outputs,
            status=status,
            error=error,
            flow_id=flow_id,
        )
        
        async with session_getter(get_db_service()) as session:
            with session.no_autoflush:
                inserted = await crud_log_transaction(session, transaction)
                if inserted:
                    print(f"✅ LOG_TRANSACTION: Successfully logged transaction_id={inserted.id}")
                    logger.debug(f"Logged transaction: {inserted.id}")
    except Exception as exc:
        print(f"❌ LOG_TRANSACTION ERROR: {exc}")
        logger.error(f"Error logging transaction: {exc!s}")


async def log_vertex_build(
    *,
    flow_id: str | UUID,
    vertex_id: str,
    valid: bool,
    params: Any,
    data: dict | None = None,
    artifacts: dict | None = None,
) -> None:
    """Asynchronously logs a vertex build record to the database if vertex build storage is enabled.

    Serializes the provided data and artifacts with configurable length and item limits before storing.
    Converts parameters to string if present. Handles exceptions by logging errors.
    
    Args:
        flow_id: The flow ID (string or UUID)
        vertex_id: The vertex ID
        valid: Whether the build was successful
        params: The vertex parameters
        data: The result data (optional)
        artifacts: The generated artifacts (optional)
    """
    try:
        print(f"🔍 LOG_VERTEX_BUILD called: vertex_id={vertex_id}, flow_id={flow_id}, valid={valid}")
        logger.info(f"LOG_VERTEX_BUILD called: vertex_id={vertex_id}, flow_id={flow_id}, valid={valid}")
        
        if not get_settings_service().settings.vertex_builds_storage_enabled:
            print(f"⚠️ LOG_VERTEX_BUILD: Storage disabled by settings")
            logger.warning("Vertex builds storage is disabled in settings")
            return
        
        try:
            if isinstance(flow_id, str):
                flow_id = UUID(flow_id)
        except ValueError:
            msg = f"Invalid flow_id passed to log_vertex_build: {flow_id!r}(type: {type(flow_id)})"
            raise ValueError(msg) from None

        vertex_build = VertexBuildBase(
            flow_id=flow_id,
            id=vertex_id,
            valid=valid,
            params=str(params) if params else None,
            data=serialize(data, max_length=get_max_text_length(), max_items=get_max_items_length()) if data else None,
            artifacts=serialize(artifacts, max_length=get_max_text_length(), max_items=get_max_items_length()) if artifacts else None,
        )
        
        async with session_getter(get_db_service()) as session:
            inserted = await crud_log_vertex_build(session, vertex_build)
            print(f"✅ LOG_VERTEX_BUILD: Successfully logged build_id={inserted.build_id}")
            logger.debug(f"Logged vertex build: {inserted.build_id}")
    except Exception as e:
        print(f"❌ LOG_VERTEX_BUILD ERROR: {e}")
        logger.exception("Error logging vertex build")
