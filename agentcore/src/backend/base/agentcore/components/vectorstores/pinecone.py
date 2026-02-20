"""
Pinecone Vector Store Component — API keys hardcoded
"""

import time
import numpy as np
from langchain_core.vectorstores import VectorStore

from agentcore.base.vectorstores.model import LCVectorStoreNode, check_cached_vector_store
from agentcore.helpers.data import docs_to_data
from agentcore.io import BoolInput, DropdownInput, HandleInput, IntInput, StrInput
from agentcore.schema.data import Data
from agentcore.schema.message import Message


PINECONE_API_KEY = "pcsk_92555_7xKAYZfyv7MXJQ4C349Y1VNDtqvui5Wu76FfSeGSyMNze6TBy9dWUD3bvuvVdv1"
GOOGLE_API_KEY = "AIzaSyC3UhBn_HLOEkvtbo1D8jhS58enFkaDjDo"



# ═══════════════════════════════════════════════════════════════

class PineconeVectorStoreNode(LCVectorStoreNode):
    display_name = "Pinecone"
    description = "Pinecone Vector Store with optional hybrid search and reranking"
    name = "Pinecone"
    icon = "Pinecone"
    inputs = [
        StrInput(name="index_name", display_name="Index Name", required=True),
        StrInput(name="namespace", display_name="Namespace", info="Namespace for the index."),
        StrInput(name="text_key", display_name="Text Key", value="text", advanced=True),
        *LCVectorStoreNode.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        BoolInput(name="auto_create_index", display_name="Auto Create Index", value=True),
        IntInput(name="embedding_dimension", display_name="Embedding Dimension", value=768),
        DropdownInput(name="cloud_provider", display_name="Cloud Provider",
                      options=["aws", "gcp", "azure"], value="aws", advanced=True),
        StrInput(name="cloud_region", display_name="Cloud Region", value="us-east-1", advanced=True),
        BoolInput(name="use_hybrid_search", display_name="Enable Hybrid Search", value=False,
                  info="Use dense + sparse vectors at RETRIEVAL time. Index must use dotproduct metric."),
        DropdownInput(name="sparse_model", display_name="Sparse Embedding Model",
                      options=["pinecone-sparse-english-v0"], value="pinecone-sparse-english-v0", advanced=True),
        StrInput(name="hybrid_alpha", display_name="Hybrid Alpha", value="0.7",
                 info="0.0 = pure sparse/keyword, 1.0 = pure dense/semantic", advanced=True),
        BoolInput(name="use_reranking", display_name="Enable Reranking", value=False),
        DropdownInput(name="rerank_model", display_name="Rerank Model",
                      options=["pinecone-rerank-v0", "bge-reranker-v2-m3", "cohere-rerank-3.5"],
                      value="pinecone-rerank-v0", advanced=True),
        IntInput(name="rerank_top_n", display_name="Rerank Top N", value=5, advanced=True),
        IntInput(name="number_of_results", display_name="Number of Results", value=4, advanced=True),
    ]

    # ══════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════

    def _get_pinecone_client(self):
        from pinecone import Pinecone
        return Pinecone(api_key=PINECONE_API_KEY)

    def _get_alpha(self) -> float:
        try:
            return float(self.hybrid_alpha)
        except (ValueError, TypeError):
            return 0.7

    def _resolve_search_query(self) -> str:
        query = self.search_query
        if query is None:
            return ""
        if isinstance(query, str):
            return query.strip()
        if isinstance(query, Message):
            return (query.text or "").strip()
        if isinstance(query, Data):
            return (query.text or "").strip()
        if isinstance(query, dict):
            return (query.get("text", "") or "").strip()
        return str(query).strip()

    # ══════════════════════════════════════════════════════════
    #  AUTO-CREATE INDEX — always dotproduct for flexibility
    # ══════════════════════════════════════════════════════════

    def _ensure_index_exists(self):
        if not self.auto_create_index:
            return
        pc = self._get_pinecone_client()
        existing = pc.list_indexes()
        names = [idx.name for idx in existing] if existing else []
        if self.index_name in names:
            return

        # Always create with dotproduct — works for both dense-only and hybrid
        from pinecone import ServerlessSpec
        pc.create_index(
            name=self.index_name,
            dimension=self.embedding_dimension,
            metric="dotproduct",
            vector_type="dense",
            spec=ServerlessSpec(cloud=self.cloud_provider, region=self.cloud_region),
        )
        for _ in range(30):
            try:
                desc = pc.describe_index(self.index_name)
                if desc.status and desc.status.get("ready", False):
                    break
            except Exception:
                pass
            time.sleep(2)

    # ══════════════════════════════════════════════════════════
    #  EMBEDDING MODEL
    # ══════════════════════════════════════════════════════════

    def _get_embedding_model(self):
        emb = self.embedding
        if hasattr(emb, "build_embeddings"):
            try:
                model = emb.build_embeddings()
                if model is not None:
                    return model
            except Exception:
                pass
        if hasattr(emb, "build"):
            try:
                model = emb.build()
                if model and hasattr(model, "embed_documents"):
                    return model
            except Exception:
                pass
        # Hardcoded fallback
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=GOOGLE_API_KEY,
            output_dimensionality=768,
        )

    # ══════════════════════════════════════════════════════════
    #  SPARSE / HYBRID HELPERS
    # ══════════════════════════════════════════════════════════

    def _generate_sparse_vectors(self, texts, input_type="passage"):
        pc = self._get_pinecone_client()
        all_sparse = []
        for i in range(0, len(texts), 96):
            batch = texts[i:i+96]
            response = pc.inference.embed(
                model=self.sparse_model, inputs=batch,
                parameters={"input_type": input_type, "truncate": "END"},
            )
            for item in response:
                indices = getattr(item, "sparse_indices", None) or getattr(item, "indices", [])
                values = getattr(item, "sparse_values", None) or getattr(item, "values", [])
                all_sparse.append({"indices": list(indices), "values": list(values)})
        return all_sparse

    def _generate_sparse_query(self, query):
        result = self._generate_sparse_vectors([query], input_type="query")
        return result[0] if result else {"indices": [], "values": []}

    @staticmethod
    def _hybrid_score_norm(dense, sparse, alpha):
        if alpha < 0 or alpha > 1:
            raise ValueError("Alpha must be between 0 and 1")
        return (
            [v * alpha for v in dense],
            {"indices": sparse["indices"], "values": [v * (1 - alpha) for v in sparse["values"]]},
        )

    # ══════════════════════════════════════════════════════════
    #  INGESTION — always dense, optionally adds sparse
    # ══════════════════════════════════════════════════════════

    def _ingest_documents(self, documents, embedder):
        """Upsert documents with dense vectors + optional sparse vectors."""
        pc = self._get_pinecone_client()
        index = pc.Index(self.index_name)
        texts = [doc.page_content for doc in documents]

        # Always generate dense embeddings
        dense_embeddings = embedder.embed_documents(texts)

        # Generate sparse vectors if hybrid is enabled
        sparse_vectors = None
        if self.use_hybrid_search:
            try:
                sparse_vectors = self._generate_sparse_vectors(texts, input_type="passage")
            except Exception as e:
                logger.warning(f"[Pinecone] Sparse embedding failed, ingesting dense-only: {e}")

        vectors = []
        for i, (doc, dense) in enumerate(zip(documents, dense_embeddings)):
            metadata = dict(doc.metadata) if doc.metadata else {}
            metadata[self.text_key] = doc.page_content[:40000]
            vec_id = f"{self.namespace or 'ns'}_{i}_{hash(doc.page_content[:50]) % 10**8}"

            vec_data = {"id": vec_id, "values": dense, "metadata": metadata}
            if sparse_vectors and i < len(sparse_vectors):
                vec_data["sparse_values"] = sparse_vectors[i]

            vectors.append(vec_data)

        for i in range(0, len(vectors), 100):
            index.upsert(vectors=vectors[i:i+100], namespace=self.namespace or "")
        return len(vectors)

    def _ingest_if_needed(self, wrapped_embeddings):
        self.ingest_data = self._prepare_ingest_data()
        if not self.ingest_data:
            return 0
        documents = []
        for doc in self.ingest_data:
            documents.append(doc.to_lc_document() if isinstance(doc, Data) else doc)
        if not documents:
            return 0
        return self._ingest_documents(documents, wrapped_embeddings)

    # ══════════════════════════════════════════════════════════
    #  BUILD VECTOR STORE
    # ══════════════════════════════════════════════════════════

    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        try:
            self._ensure_index_exists()
        except Exception as e:
            raise ValueError(f"Error creating index: {e}") from e

        from langchain_pinecone import PineconeVectorStore

        real_embedding = self._get_embedding_model()
        wrapped = Float32Embeddings(real_embedding)

        pinecone = PineconeVectorStore(
            index_name=self.index_name,
            embedding=wrapped,
            text_key=self.text_key,
            namespace=self.namespace,
            pinecone_api_key=PINECONE_API_KEY,
        )

        try:
            count = self._ingest_if_needed(wrapped)
            if count > 0:
                self.status = f"Ingested {count} document(s)"
        except Exception as e:
            raise ValueError(f"Error ingesting documents: {e}") from e

        return pinecone

    # ══════════════════════════════════════════════════════════
    #  SEARCH — hybrid and reranking are retrieval-time options
    # ══════════════════════════════════════════════════════════

    def search_documents(self) -> list[Data]:
        query = self._resolve_search_query()
        if not query:
            self.status = "No search query provided."
            return []

        try:
            self._ensure_index_exists()
        except Exception as e:
            raise ValueError(f"Error ensuring index: {e}") from e

        real_embedding = self._get_embedding_model()
        wrapped = Float32Embeddings(real_embedding)

        # Ingest pending documents
        try:
            count = self._ingest_if_needed(wrapped)
            if count > 0:
                time.sleep(1)
        except Exception as e:
            raise ValueError(f"Error ingesting: {e}") from e

        # ── Determine retrieval method ─────────────────────
        retrieve_k = self.number_of_results
        if self.use_reranking:
            retrieve_k = max(self.number_of_results, 20)

        search_method = "dense"
        scores_map = {}

        try:
            if self.use_hybrid_search:
                docs, scores_map = self._hybrid_search(query, wrapped, k=retrieve_k)
                search_method = f"hybrid (alpha={self._get_alpha()})"
            else:
                docs, scores_map = self._dense_search(query, wrapped, k=retrieve_k)
                search_method = "dense"
        except Exception as e:
            raise ValueError(f"Error searching: {type(e).__name__}: {e}") from e

        # ── Reranking ──────────────────────────────────────
        rerank_info = "disabled"
        if self.use_reranking and docs:
            try:
                docs, rerank_scores = self._rerank_documents(query, docs)
                rerank_info = f"{self.rerank_model} (top {len(docs)})"
                # Update scores with rerank scores
                scores_map = rerank_scores
            except Exception as e:
                rerank_info = f"failed: {e}"
                logger.warning(f"[Pinecone] Reranking failed: {e}")

        # ── Build output with metadata ─────────────────────
        data = self._build_output(docs, scores_map, search_method, rerank_info, query)
        self.status = f"{len(data)} result(s) | method={search_method} | rerank={rerank_info}"
        return data

    def _dense_search(self, query, wrapped_embeddings, k=10):
        """Pure dense vector search."""
        from langchain_core.documents import Document
        pc = self._get_pinecone_client()
        index = pc.Index(self.index_name)

        dense_vector = wrapped_embeddings.embed_query(query)
        results = index.query(
            namespace=self.namespace or "",
            top_k=k,
            vector=dense_vector,
            include_metadata=True,
        )

        docs = []
        scores_map = {}
        for match in results.get("matches", []):
            metadata = match.get("metadata", {})
            text = metadata.pop(self.text_key, "")
            score = match.get("score", 0.0)
            doc = Document(page_content=text, metadata=metadata)
            docs.append(doc)
            scores_map[id(doc)] = {"score": round(score, 4), "type": "dense"}

        return docs, scores_map

    def _hybrid_search(self, query, wrapped_embeddings, k=10):
        """Hybrid dense + sparse search."""
        from langchain_core.documents import Document
        pc = self._get_pinecone_client()
        index = pc.Index(self.index_name)

        dense_vector = wrapped_embeddings.embed_query(query)
        sparse_vector = self._generate_sparse_query(query)

        alpha = self._get_alpha()
        hdense, hsparse = self._hybrid_score_norm(dense_vector, sparse_vector, alpha)

        results = index.query(
            namespace=self.namespace or "",
            top_k=k,
            vector=hdense,
            sparse_vector=hsparse,
            include_metadata=True,
        )

        docs = []
        scores_map = {}
        for match in results.get("matches", []):
            metadata = match.get("metadata", {})
            text = metadata.pop(self.text_key, "")
            score = match.get("score", 0.0)
            doc = Document(page_content=text, metadata=metadata)
            docs.append(doc)
            scores_map[id(doc)] = {
                "score": round(score, 4),
                "type": "hybrid",
                "alpha": alpha,
            }

        return docs, scores_map

    def _rerank_documents(self, query, docs):
        """Rerank documents and return new scores."""
        pc = self._get_pinecone_client()
        rerank_input = [
            {"id": str(i), "text": doc.page_content if hasattr(doc, "page_content") else str(doc)}
            for i, doc in enumerate(docs)
        ][:100]

        response = pc.inference.rerank(
            model=self.rerank_model, query=query, documents=rerank_input,
            top_n=min(self.rerank_top_n, len(rerank_input)),
            return_documents=True, parameters={"truncate": "END"},
        )

        reranked_docs = []
        rerank_scores = {}
        for rank, r in enumerate(response.data):
            if r.index < len(docs):
                doc = docs[r.index]
                reranked_docs.append(doc)
                rerank_scores[id(doc)] = {
                    "rerank_score": round(r.score, 4),
                    "rerank_position": rank + 1,
                    "rerank_model": self.rerank_model,
                    "type": "reranked",
                }

        return reranked_docs, rerank_scores

    def _build_output(self, docs, scores_map, search_method, rerank_info, query):
        """Build Data output with search metadata and scores."""
        results = []
        for rank, doc in enumerate(docs):
            text = doc.page_content if hasattr(doc, "page_content") else str(doc)
            metadata = doc.metadata if hasattr(doc, "metadata") else {}

            # Get score info for this doc
            score_info = scores_map.get(id(doc), {})

            # Build rich metadata
            result_data = {
                "text": text,
                "rank": rank + 1,
                "search_method": search_method,
                "reranking": rerank_info,
                "query": query,
                **score_info,
                **metadata,
            }

            results.append(Data(text=text, data=result_data))

        return results


# ═══════════════════════════════════════════════════════════════

class Float32Embeddings:
    """Wrapper that ensures float32 output."""
    def __init__(self, real_model):
        self._model = real_model

    def embed_documents(self, texts):
        embeddings = self._model.embed_documents(texts)
        return [[float(np.float32(x)) for x in vec] for vec in embeddings]

    def embed_query(self, text):
        embedding = self._model.embed_query(text)
        return [float(np.float32(x)) for x in embedding]