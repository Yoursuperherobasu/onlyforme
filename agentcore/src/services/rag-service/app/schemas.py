"""Pydantic schemas for the RAG microservice API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Pinecone — Document primitives
# ---------------------------------------------------------------------------


class DocumentItem(BaseModel):
    page_content: str
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pinecone — Ingest
# ---------------------------------------------------------------------------


class PineconeIngestRequest(BaseModel):
    index_name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    namespace: str = Field(default="", max_length=256)
    text_key: str = "text"
    documents: list[DocumentItem] = Field(..., max_length=10000)
    embedding_vectors: list[list[float]] = Field(..., max_length=10000)
    auto_create_index: bool = True
    embedding_dimension: int = Field(default=768, ge=1, le=20000)
    cloud_provider: str = "aws"
    cloud_region: str = "us-east-1"
    use_hybrid_search: bool = False
    sparse_model: str = "pinecone-sparse-english-v0"

    @field_validator("embedding_vectors")
    @classmethod
    def vectors_match_documents(cls, v, info):
        docs = info.data.get("documents")
        if docs is not None and len(v) != len(docs):
            raise ValueError(f"embedding_vectors length ({len(v)}) must match documents length ({len(docs)})")
        return v


class PineconeIngestResponse(BaseModel):
    vectors_upserted: int
    index_name: str
    namespace: str


# ---------------------------------------------------------------------------
# Pinecone — Search
# ---------------------------------------------------------------------------


class PineconeSearchRequest(BaseModel):
    index_name: str = Field(..., min_length=1, max_length=128)
    namespace: str = Field(default="", max_length=256)
    text_key: str = "text"
    query: str = Field(..., min_length=1, max_length=10000)
    query_embedding: list[float]
    number_of_results: int = Field(default=4, ge=1, le=100)
    use_hybrid_search: bool = False
    sparse_model: str = "pinecone-sparse-english-v0"
    hybrid_alpha: float = Field(default=0.7, ge=0.0, le=1.0)
    use_reranking: bool = False
    rerank_model: str = "pinecone-rerank-v0"
    rerank_top_n: int = Field(default=5, ge=1, le=100)


class PineconeSearchResultItem(BaseModel):
    text: str
    metadata: dict = Field(default_factory=dict)
    score: float = 0.0
    score_info: dict = Field(default_factory=dict)
    rank: int = 0


class PineconeSearchResponse(BaseModel):
    results: list[PineconeSearchResultItem]
    search_method: str
    rerank_info: str = "disabled"


# ---------------------------------------------------------------------------
# Pinecone — Ensure index
# ---------------------------------------------------------------------------


class EnsureIndexRequest(BaseModel):
    index_name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    embedding_dimension: int = Field(default=768, ge=1, le=20000)
    cloud_provider: str = "aws"
    cloud_region: str = "us-east-1"


class EnsureIndexResponse(BaseModel):
    exists: bool
    created: bool
    index_name: str


# ---------------------------------------------------------------------------
# Pinecone — Test connection
# ---------------------------------------------------------------------------


class PineconeTestConnectionRequest(BaseModel):
    pinecone_api_key: str | None = None


class PineconeTestConnectionResponse(BaseModel):
    success: bool
    message: str
    indexes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Graph RAG — Entity / Relationship primitives
# ---------------------------------------------------------------------------


class RelationshipItem(BaseModel):
    target: str
    target_type: str = "Entity"
    type: str = "RELATED_TO"
    description: str = Field(default="", max_length=5000)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class EntityItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=1000)
    type: str = "Entity"
    description: str = Field(default="", max_length=10000)
    relationships: list[RelationshipItem] = Field(default_factory=list, max_length=500)
    source_chunk_id: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
    graph_kb_id: str = "default"
    id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    importance: float | None = None


# ---------------------------------------------------------------------------
# Graph RAG — Ingest
# ---------------------------------------------------------------------------


class GraphIngestRequest(BaseModel):
    entities: list[EntityItem] = Field(..., max_length=5000)
    graph_kb_id: str = Field(default="default", min_length=1, max_length=256)


class GraphIngestResponse(BaseModel):
    entities_created: int
    relationships_created: int
    graph_kb_id: str


# ---------------------------------------------------------------------------
# Graph RAG — Embed entities
# ---------------------------------------------------------------------------


class EntityEmbeddingPair(BaseModel):
    element_id: str
    embedding: list[float]


class EmbedEntitiesRequest(BaseModel):
    graph_kb_id: str = "default"
    embeddings: list[EntityEmbeddingPair]


class EmbedEntitiesResponse(BaseModel):
    entities_embedded: int
    graph_kb_id: str


class FetchUnembeddedRequest(BaseModel):
    graph_kb_id: str = "default"
    batch_size: int = Field(default=200, ge=1, le=1000)


class UnembeddedEntity(BaseModel):
    name: str
    description: str
    element_id: str


class FetchUnembeddedResponse(BaseModel):
    entities: list[UnembeddedEntity]


# ---------------------------------------------------------------------------
# Graph RAG — Ensure vector index
# ---------------------------------------------------------------------------


class EnsureVectorIndexRequest(BaseModel):
    graph_kb_id: str = "default"


class EnsureVectorIndexResponse(BaseModel):
    success: bool
    dimension: int | None = None
    message: str = ""


# ---------------------------------------------------------------------------
# Graph RAG — Search
# ---------------------------------------------------------------------------


class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    query_embedding: list[float] | None = None
    graph_kb_id: str = Field(default="default", min_length=1, max_length=256)
    search_type: str = "vector_similarity"
    number_of_results: int = Field(default=10, ge=1, le=100)
    expansion_hops: int = Field(default=2, ge=1, le=3)
    include_source_chunks: bool = True


class GraphSearchResultItem(BaseModel):
    text: str
    entity_name: str
    entity_type: str
    entity_description: str = ""
    score: float = 0.0
    neighbors: list[dict] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)
    search_type: str = "vector_similarity"
    graph_kb_id: str = "default"


class GraphSearchResponse(BaseModel):
    results: list[GraphSearchResultItem]
    search_type: str
    graph_kb_id: str


# ---------------------------------------------------------------------------
# Graph RAG — Stats
# ---------------------------------------------------------------------------


class StatsRequest(BaseModel):
    graph_kb_id: str = "default"


class StatsResponse(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    community_count: int = 0
    graph_kb_id: str = "default"


# ---------------------------------------------------------------------------
# Graph RAG — Community detection
# ---------------------------------------------------------------------------


class CommunitySummaryInput(BaseModel):
    community_id: str
    title: str
    summary: str
    members: list[str] = Field(default_factory=list)
    node_count: int = 0


class CommunityDetectRequest(BaseModel):
    graph_kb_id: str = "default"
    max_communities: int = Field(default=10, ge=1, le=50)
    min_community_size: int = Field(default=2, ge=2, le=100)
    community_summaries: list[CommunitySummaryInput] | None = None


class CommunityItem(BaseModel):
    community_id: str
    title: str = ""
    summary: str = ""
    node_count: int = 0
    members: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    graph_kb_id: str = "default"
    needs_summary: bool = False


class CommunityDetectResponse(BaseModel):
    communities: list[CommunityItem]


class StoreCommunityRequest(BaseModel):
    graph_kb_id: str = "default"
    communities: list[CommunitySummaryInput]


class StoreCommunityResponse(BaseModel):
    stored: int


# ---------------------------------------------------------------------------
# Graph RAG — Test connection
# ---------------------------------------------------------------------------


class GraphTestConnectionRequest(BaseModel):
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str | None = None


class GraphTestConnectionResponse(BaseModel):
    success: bool
    message: str
    node_count: int = 0
