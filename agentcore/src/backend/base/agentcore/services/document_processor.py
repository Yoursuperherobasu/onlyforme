"""Document processor service for orchestrator document Q&A.

Orchestrates the RAG pipeline:
  extract text → chunk → embed → ingest into Pinecone → search → build context

Uses existing agentcore infrastructure:
  - document_extractor.py for text extraction
  - ltm/embeddings.py for embedding generation
  - pinecone_service_client.py for vector store operations
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from loguru import logger


# ---------------------------------------------------------------------------
# Text chunking (simple recursive splitter)
# ---------------------------------------------------------------------------

def _chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks.

    Uses paragraph/sentence boundaries when possible.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # Split on paragraph boundaries first
    separators = ["\n\n", "\n", ". ", " "]
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Find the best split point near the end
        best_split = end
        for sep in separators:
            # Look backward from end for a separator
            idx = text.rfind(sep, start + chunk_size // 2, end)
            if idx > start:
                best_split = idx + len(sep)
                break

        chunk = text[start:best_split].strip()
        if chunk:
            chunks.append(chunk)

        # Move start with overlap
        start = best_split - chunk_overlap
        if start < 0:
            start = 0
        # Avoid infinite loop
        if start >= best_split:
            start = best_split

    return chunks


def _make_chunk_id(session_id: str, source_file: str, chunk_index: int, content: str) -> str:
    """Generate a deterministic chunk ID for idempotent ingestion."""
    raw = f"{session_id}:{source_file}:{chunk_index}:{content[:100]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _get_settings():
    from agentcore.services.deps import get_settings_service
    return get_settings_service().settings


# ---------------------------------------------------------------------------
# Ingest documents into Pinecone
# ---------------------------------------------------------------------------

async def process_and_ingest(
    file_paths: list[str],
    session_id: str,
) -> int:
    """Extract text from files, chunk, embed, and ingest into Pinecone.

    Args:
        file_paths: List of storage-relative file paths.
        session_id: Chat session ID (used as Pinecone namespace).

    Returns:
        Number of chunks ingested.
    """
    from agentcore.services.document_extractor import extract_text
    from agentcore.services.ltm.embeddings import embed_batch
    from agentcore.services.pinecone_service_client import async_ingest_via_service

    settings = _get_settings()
    index_name = settings.doc_qa_pinecone_index
    chunk_size = settings.doc_qa_chunk_size
    chunk_overlap = settings.doc_qa_chunk_overlap

    all_chunks: list[str] = []
    all_documents: list[dict] = []
    all_ids: list[str] = []

    for file_path in file_paths:
        file_name = Path(file_path).name
        logger.info(f"[DocQA] Extracting text from: {file_name}")

        text = await extract_text(file_path)
        if not text.strip() or text.startswith("[ERROR]") or text.startswith("[Unsupported"):
            logger.warning(f"[DocQA] Skipping {file_name}: {text[:100]}")
            continue

        chunks = _chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        logger.info(f"[DocQA] {file_name}: {len(chunks)} chunks created")

        for i, chunk in enumerate(chunks):
            chunk_id = _make_chunk_id(session_id, file_name, i, chunk)
            all_chunks.append(chunk)
            all_documents.append({
                "text": chunk,
                "source_file": file_name,
                "chunk_index": i,
                "session_id": session_id,
            })
            all_ids.append(chunk_id)

    if not all_chunks:
        logger.warning("[DocQA] No text extracted from any files")
        return 0

    # Generate embeddings in batches
    logger.info(f"[DocQA] Generating embeddings for {len(all_chunks)} chunks")
    batch_size = 50
    all_embeddings: list[list[float]] = []

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        embeddings = await embed_batch(batch)
        if not embeddings:
            logger.error("[DocQA] Embedding generation failed — check LTM_EMBEDDING_API_KEY")
            return 0
        all_embeddings.extend(embeddings)

    if len(all_embeddings) != len(all_chunks):
        logger.error(f"[DocQA] Embedding count mismatch: {len(all_embeddings)} vs {len(all_chunks)}")
        return 0

    # Determine embedding dimension from first vector
    embedding_dim = len(all_embeddings[0]) if all_embeddings else 1536

    # Ingest into Pinecone
    logger.info(f"[DocQA] Ingesting {len(all_chunks)} chunks into Pinecone index={index_name} namespace={session_id}")
    try:
        result = await async_ingest_via_service(
            index_name=index_name,
            namespace=session_id,
            text_key="text",
            documents=all_documents,
            embedding_vectors=all_embeddings,
            auto_create_index=True,
            embedding_dimension=embedding_dim,
            vector_ids=all_ids,
        )
        count = result.get("upserted_count", len(all_chunks))
        logger.info(f"[DocQA] Successfully ingested {count} chunks")
        return count
    except Exception as e:
        logger.error(f"[DocQA] Pinecone ingestion failed: {e}")
        return 0


# ---------------------------------------------------------------------------
# Search documents in Pinecone
# ---------------------------------------------------------------------------

async def search_documents(
    query: str,
    session_id: str,
    top_k: int | None = None,
) -> list[str]:
    """Search Pinecone for relevant document chunks.

    Args:
        query: User's question.
        session_id: Chat session ID (Pinecone namespace).
        top_k: Number of chunks to retrieve (defaults to settings).

    Returns:
        List of relevant text chunks.
    """
    from agentcore.services.ltm.embeddings import embed_single
    from agentcore.services.pinecone_service_client import async_search_via_service

    settings = _get_settings()
    index_name = settings.doc_qa_pinecone_index
    if top_k is None:
        top_k = settings.doc_qa_top_k

    # Generate query embedding
    query_embedding = await embed_single(query)
    if not query_embedding:
        logger.warning("[DocQA] Failed to generate query embedding")
        return []

    try:
        result = await async_search_via_service(
            index_name=index_name,
            namespace=session_id,
            text_key="text",
            query=query,
            query_embedding=query_embedding,
            number_of_results=top_k,
        )

        matches = result.get("matches", [])
        chunks = []
        for match in matches:
            text = match.get("metadata", {}).get("text", "")
            if text:
                chunks.append(text)

        logger.info(f"[DocQA] Found {len(chunks)} relevant chunks for query")
        return chunks

    except Exception as e:
        logger.error(f"[DocQA] Pinecone search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Build document Q&A prompt
# ---------------------------------------------------------------------------

def build_doc_qa_prompt(query: str, chunks: list[str]) -> str:
    """Build an LLM prompt with document context.

    Args:
        query: User's original question.
        chunks: Retrieved document chunks.

    Returns:
        Enriched prompt with document context.
    """
    if not chunks:
        return query

    context = "\n\n---\n\n".join(chunks)
    return (
        "You are answering questions based on the uploaded documents. "
        "Use ONLY the following document context to answer. "
        "If the answer is not in the context, say so.\n\n"
        f"## Document Context\n\n{context}\n\n"
        f"## Question\n\n{query}"
    )


# ---------------------------------------------------------------------------
# Session cleanup
# ---------------------------------------------------------------------------

async def cleanup_session_docs(session_id: str) -> None:
    """Delete all document vectors for a session from Pinecone.

    Called when a session is deleted or archived.
    """
    from agentcore.services.pinecone_service_client import delete_namespace_via_service

    settings = _get_settings()
    index_name = settings.doc_qa_pinecone_index

    try:
        delete_namespace_via_service(index_name=index_name, namespace=session_id)
        logger.info(f"[DocQA] Cleaned up Pinecone namespace for session {session_id}")
    except Exception as e:
        logger.warning(f"[DocQA] Failed to cleanup Pinecone namespace for session {session_id}: {e}")


# ---------------------------------------------------------------------------
# Check if session has documents
# ---------------------------------------------------------------------------

async def session_has_documents(session_id: str) -> bool:
    """Check if a session has any documents ingested in Pinecone.

    Used for follow-up questions without new file uploads.
    """
    # A simple way: try a dummy search and see if any results come back
    try:
        chunks = await search_documents("document", session_id, top_k=1)
        return len(chunks) > 0
    except Exception:
        return False
