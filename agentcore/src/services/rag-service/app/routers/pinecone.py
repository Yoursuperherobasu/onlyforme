"""Pinecone vector store endpoints."""

from __future__ import annotations

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_api_key
from app.schemas import (
    EnsureIndexRequest,
    EnsureIndexResponse,
    PineconeIngestRequest,
    PineconeIngestResponse,
    PineconeSearchRequest,
    PineconeSearchResponse,
    PineconeTestConnectionRequest,
    PineconeTestConnectionResponse,
)
from app.services.pinecone_service import (
    ensure_index,
    ingest_documents,
    search_documents,
    test_connection,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/pinecone", tags=["Pinecone"], dependencies=[Depends(verify_api_key)])


async def _run_sync(func, *args):
    """Run a blocking function in the default executor to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


def _extract_error(e: Exception) -> str:
    """Extract a human-readable error message from Pinecone or other exceptions."""
    body = getattr(e, "body", None)
    if body:
        if isinstance(body, str):
            return body
        if isinstance(body, dict):
            err = body.get("error", {})
            if isinstance(err, dict):
                return err.get("message", str(e))
            return str(err)
    return str(e)


@router.post("/ensure-index", response_model=EnsureIndexResponse)
async def ensure_index_endpoint(req: EnsureIndexRequest):
    try:
        return await _run_sync(ensure_index, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        detail = _extract_error(e)
        logger.error("ensure_index failed: %s", detail)
        raise HTTPException(status_code=502, detail=f"Pinecone error: {detail}")


@router.post("/ingest", response_model=PineconeIngestResponse)
async def ingest_endpoint(req: PineconeIngestRequest):
    try:
        return await _run_sync(ingest_documents, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        detail = _extract_error(e)
        logger.error("ingest failed: %s", detail)
        raise HTTPException(status_code=502, detail=f"Pinecone error: {detail}")


@router.post("/search", response_model=PineconeSearchResponse)
async def search_endpoint(req: PineconeSearchRequest):
    try:
        return await _run_sync(search_documents, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        detail = _extract_error(e)
        logger.error("search failed: %s", detail)
        raise HTTPException(status_code=502, detail=f"Pinecone error: {detail}")


@router.post("/test-connection", response_model=PineconeTestConnectionResponse)
async def test_connection_endpoint(req: PineconeTestConnectionRequest):
    return await _run_sync(test_connection, req)
