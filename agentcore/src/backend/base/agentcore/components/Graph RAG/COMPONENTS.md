# Graph RAG — Canvas Components Documentation

This document covers all Graph RAG canvas components that form the knowledge-graph ingestion and retrieval pipeline in AgentCore.

---

## Pipeline Overview

```
Documents
    │
    ▼
┌──────────────────────┐
│  Graph Schema Config  │  ← Define ontology (entity types, relationship types)
└──────────┬───────────┘
           │ schema
           ▼
┌──────────────────────┐
│ Graph Entity Extractor│  ← LLM extracts entities & relationships from text
└──────────┬───────────┘
           │ raw entities
           ▼
┌──────────────────────┐
│   Entity Resolver     │  ← Deduplicate entities across chunks
└──────────┬───────────┘
           │ resolved entities
           ▼
┌──────────────────────┐
│  Graph Transformer    │  ← Normalize, filter, score, clean graph data
└──────────┬───────────┘
           │ clean entities
           ▼
┌──────────────────────┐
│  Neo4j Graph Store    │  ← Persist to Neo4j via graph-rag-service (port 8004)
└──────────┬───────────┘
           │ stored graph
           ▼
┌──────────────────────────┐
│ Graph Community Search    │  ← Detect communities, generate LLM summaries
│                           │     via graph-rag-service (port 8004)
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────┐
│  Graph RAG Retriever  │  ← Query-time: merge graph + vector results
└──────────────────────┘
```

**Microservice delegation**: Only `Neo4j Graph Store` and `Graph Community Search` make HTTP calls to the graph-rag-service microservice. All other components run pure local logic (LLM calls or data transformations).

---

## 1. Graph Schema Config

**File**: `graph_schema_config.py`
**Class**: `GraphSchemaConfigComponent`
**Purpose**: Define the ontology (allowed entity types, relationship types, and constraints) that guides entity extraction and graph transformation.

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `domain_template` | Dropdown | Pre-built template: General, Corporate, Legal, Healthcare, IT/Software, Custom |
| `custom_entity_types` | String (optional) | Comma-separated entity types for Custom mode |
| `custom_relationship_types` | String (optional) | Comma-separated relationship types for Custom mode |
| `strict_mode` | Boolean | If true, only allow schema-defined types |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `schema` | `Data` | Structured schema object with `entity_types`, `relationship_types`, `strict_mode` |

### Domain Templates

- **General**: Person, Organization, Location, Event, Concept, Product, Technology
- **Corporate**: Employee, Department, Project, Client, Contract, KPI, Policy
- **Legal**: Party, Court, Statute, Case, Regulation, Jurisdiction, Filing
- **Healthcare**: Patient, Provider, Diagnosis, Medication, Procedure, Facility
- **IT/Software**: Service, API, Database, Server, Application, Repository, Pipeline, Vulnerability

### Notes

- No external calls — pure configuration component
- Output is consumed by `Graph Entity Extractor` (to guide extraction prompts) and `Graph Transformer` (to enforce schema constraints)

---

## 2. Graph Entity Extractor

**File**: `graph_entity_extractor.py`
**Class**: `GraphEntityExtractorComponent`
**Purpose**: Use an LLM to extract entities and relationships from text chunks. This is the core NLP step that converts unstructured text into structured graph data.

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `data_inputs` | `list[Data]` | Text chunks to process (each must have a `text` field) |
| `llm` | LLM Handle | Connected LLM node (e.g., GPT-4, Claude) for extraction |
| `schema` | `Data` (optional) | Schema from Graph Schema Config — guides which types to extract |
| `extraction_prompt` | Multiline String | Customizable system prompt for LLM extraction |
| `max_entities_per_chunk` | Integer | Cap on entities per chunk (default: 50) |
| `deduplication_strategy` | Dropdown | `none`, `exact`, `fuzzy` — how to deduplicate within a single chunk |
| `include_source_context` | Boolean | Whether to attach source text to each entity |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `entities` | `list[Data]` | Each Data item represents an entity with: `name`, `type`, `description`, `relationships` (list of `{target, type, description}`), `source_chunk_id`, `aliases` |

### How It Works

1. For each input chunk, builds a prompt incorporating the schema (if provided) and the chunk text
2. Sends to the connected LLM with structured output instructions
3. Parses the LLM JSON response into entity objects
4. Applies within-chunk deduplication (exact name match or fuzzy via `difflib.SequenceMatcher`)
5. Attaches `source_chunk_id` from the input Data's `id` field
6. Returns flat list of all entities across all chunks

### Notes

- No microservice calls — LLM invocation happens locally via the connected LLM node
- Schema-aware: if a schema is connected, the prompt explicitly lists allowed entity/relationship types
- Handles LLM JSON parsing errors gracefully with retry logic

---

## 3. Entity Resolver

**File**: `entity_resolver.py`
**Class**: `EntityResolverComponent`
**Purpose**: Deduplicate entities that were extracted independently from different chunks. Merges duplicate entities into canonical forms.

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `entities` | `list[Data]` | Raw entities from Entity Extractor |
| `strategy` | Dropdown | `exact_fuzzy`, `fuzzy_only`, `llm_assisted`, `embedding_similarity` |
| `fuzzy_threshold` | Float | Similarity threshold for fuzzy matching (default: 0.85) |
| `llm` | LLM Handle (optional) | Required only for `llm_assisted` strategy |
| `embedding_model` | Embedding Handle (optional) | Required only for `embedding_similarity` strategy |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `resolved_entities` | `list[Data]` | Deduplicated entities with merged metadata |

### Strategies

| Strategy | How It Works |
|----------|-------------|
| **Exact + Fuzzy** | Groups by exact normalized name, then merges fuzzy-similar groups (SequenceMatcher) |
| **Fuzzy Only** | Pairwise fuzzy comparison of all entity names |
| **LLM-Assisted** | Sends candidate pairs to LLM asking "are these the same entity?" |
| **Embedding Similarity** | Computes embeddings of entity names, clusters by cosine similarity |

### Merge Behavior

When two entities are identified as duplicates:
- **Name**: keeps the longest variant
- **Type**: keeps the most common type across duplicates
- **Description**: concatenates all unique descriptions
- **Relationships**: unions all relationships (deduped by target+type)
- **Source chunk IDs**: unions all source references
- **Aliases**: collects all name variants

### Notes

- No microservice calls — all logic runs locally
- LLM and Embedding strategies are optional and require the respective node to be connected on the canvas

---

## 4. Graph Transformer

**File**: `graph_transformer.py`
**Class**: `GraphTransformerComponent`
**Purpose**: Post-processing pipeline that normalizes, filters, and scores entities before they are stored in Neo4j.

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `entities` | `list[Data]` | Resolved entities from Entity Resolver |
| `schema` | `Data` (optional) | Schema from Graph Schema Config |
| `normalize_names` | Boolean | Title-case entity names, strip whitespace (default: true) |
| `blocked_names` | String | Comma-separated names to filter out (e.g., "unknown, n/a, none") |
| `blocked_types` | String | Comma-separated types to filter out |
| `enforce_schema` | Boolean | Drop entities/relationships whose types aren't in the schema (default: false) |
| `compute_importance` | Boolean | Calculate importance score per entity (default: true) |
| `remove_self_loops` | Boolean | Remove relationships where source == target (default: true) |
| `remove_orphans` | Boolean | Remove entities with zero relationships (default: false) |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `transformed_entities` | `list[Data]` | Clean, scored entities ready for storage |

### Processing Pipeline (in order)

1. **Normalize names** — title-case, strip whitespace, collapse internal spaces
2. **Filter blocked names** — remove entities matching blocked list (case-insensitive)
3. **Filter blocked types** — remove entities matching blocked type list
4. **Enforce schema** — if schema connected and `enforce_schema=true`, drop non-conforming types
5. **Compute importance** — score = weighted sum of: relationship count, description length, source chunk count, alias count
6. **Remove self-loops** — drop relationships where source entity == target entity
7. **Remove orphans** — drop entities with no remaining relationships

### Notes

- No microservice calls — pure data transformation
- Importance scores are normalized to [0, 1] range across the batch

---

## 5. Neo4j Graph Store

**File**: `neo4j_graph_store.py`
**Class**: `Neo4jGraphStoreComponent`
**Purpose**: Persist entities and relationships into Neo4j, manage embeddings, and perform graph search. **Delegates all Neo4j operations to the graph-rag-service microservice (port 8004).**

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `entities` | `list[Data]` | Transformed entities to store |
| `embedding_model` | Embedding Handle | Connected embedding node for vector operations |
| `neo4j_uri` | String | Neo4j connection URI (passed to microservice) |
| `neo4j_username` | String | Neo4j username |
| `neo4j_password` | SecretString | Neo4j password |
| `neo4j_database` | String | Neo4j database name (default: "neo4j") |
| `search_query` | String (optional) | Query for search mode |
| `search_type` | Dropdown | `vector`, `keyword`, `hybrid` |
| `top_k` | Integer | Number of results to return (default: 10) |
| `mode` | Dropdown | `ingest`, `search`, `both` |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `stored_count` | `Data` | Number of entities stored (ingest mode) |
| `search_results` | `list[Data]` | Search results with scores (search mode) |

### Microservice Calls

| Operation | Client Function | Service Endpoint |
|-----------|----------------|-----------------|
| Store entities + relationships | `ingest_via_service()` | `POST /v1/graph/ingest` |
| Get entities without embeddings | `fetch_unembedded_via_service()` | `POST /v1/graph/fetch-unembedded` |
| Store computed embeddings | `store_embeddings_via_service()` | `POST /v1/graph/store-embeddings` |
| Create vector index | `ensure_vector_index_via_service()` | `POST /v1/graph/ensure-vector-index` |
| Search graph | `search_via_service()` | `POST /v1/graph/search` |

### Embedding Loop

After ingestion, the component runs an embedding loop locally:

1. Calls `fetch_unembedded_via_service()` to get entities without embeddings
2. Generates embeddings locally using the connected embedding node
3. Calls `store_embeddings_via_service()` to persist the vectors
4. Calls `ensure_vector_index_via_service()` to create/update the Neo4j vector index

**Key design**: Embedding generation stays in the backend (using the user's chosen embedding model). Only the storage and indexing are delegated to the microservice.

### Neo4j Graph Schema

Nodes:
- `__Entity__` — `name`, `type`, `description`, `embedding` (vector), `source_chunk_ids`, `importance`
- `__Chunk__` — `text`, `chunk_id`, `embedding`

Relationships:
- `(:__Entity__)-[:RELATED_TO {type, description}]->(:__Entity__)`
- `(:__Chunk__)-[:MENTIONS]->(:__Entity__)`

---

## 6. Graph Community Search

**File**: `graph_community_search.py`
**Class**: `GraphCommunitySearchComponent`
**Purpose**: Detect communities of related entities, generate LLM summaries for each community, and perform global search using MAP/REDUCE over community summaries. **Delegates community detection and storage to the graph-rag-service microservice (port 8004).**

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `llm` | LLM Handle | Connected LLM for generating community summaries and answering queries |
| `neo4j_uri` | String | Neo4j connection URI |
| `neo4j_username` | String | Neo4j username |
| `neo4j_password` | SecretString | Neo4j password |
| `neo4j_database` | String | Neo4j database name (default: "neo4j") |
| `query` | String | User query for global search |
| `mode` | Dropdown | `detect_communities`, `global_search`, `both` |
| `community_summary_prompt` | Multiline String | Prompt template for summarizing communities |
| `map_prompt` | Multiline String | MAP step prompt for global search |
| `reduce_prompt` | Multiline String | REDUCE step prompt for global search |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `communities` | `list[Data]` | Detected communities with summaries |
| `answer` | `Data` | Final answer from global search |

### Community Detection Flow

1. Calls `detect_communities_via_service()` → microservice runs Union-Find on the Neo4j graph and returns raw community groups
2. For each community, builds a text description from member entities
3. Sends each description to the connected LLM to generate a human-readable summary
4. Calls `store_communities_via_service()` → microservice persists `__Community__` nodes with `HAS_MEMBER` relationships

**Key design**: Community detection algorithm (Union-Find) runs in the microservice. LLM summary generation runs locally.

### Global Search (MAP/REDUCE)

1. **MAP phase**: For each community summary, asks the LLM: "Given this community, what information is relevant to the query?"
2. **REDUCE phase**: Combines all MAP outputs and asks the LLM to synthesize a final comprehensive answer

This enables answering broad questions that span the entire knowledge graph (e.g., "What are the main themes in this document corpus?").

### Neo4j Schema Additions

- `__Community__` — `community_id`, `title`, `summary`, `member_count`
- `(:__Community__)-[:HAS_MEMBER]->(:__Entity__)`

---

## 7. Graph RAG Retriever

**File**: `graph_rag_retriever.py`
**Class**: `GraphRAGRetrieverComponent`
**Purpose**: Query-time component that merges graph search results with optional vector store results into a unified context for the LLM.

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `graph_results` | `list[Data]` | Search results from Neo4j Graph Store |
| `vector_results` | `list[Data]` (optional) | Search results from a vector store (e.g., Pinecone) |
| `query` | String | The user's query |
| `strategy` | Dropdown | `graph_first`, `vector_first`, `interleaved`, `score_weighted` |
| `max_results` | Integer | Total results to return (default: 10) |
| `graph_weight` | Float | Weight for graph results in score_weighted mode (default: 0.6) |
| `context_template` | Multiline String | Template for formatting the final context string |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `context` | `Data` | Merged and formatted context ready for LLM consumption |
| `sources` | `list[Data]` | Individual source items with provenance metadata |

### Merge Strategies

| Strategy | Behavior |
|----------|----------|
| **Graph First** | All graph results first, then vector results to fill remaining slots |
| **Vector First** | All vector results first, then graph results to fill remaining slots |
| **Interleaved** | Alternates: graph[0], vector[0], graph[1], vector[1], ... |
| **Score Weighted** | Normalizes scores from both sources, applies `graph_weight` vs `1-graph_weight`, sorts by weighted score |

### Notes

- No microservice calls — pure merging and formatting logic
- Graph results and vector results must be connected from their respective store components on the canvas
- The `context_template` supports placeholders: `{query}`, `{context}`, `{sources}`

---

## Component Dependency Map

```
Component                  │ LLM? │ Embeddings? │ Microservice?        │ Neo4j?
───────────────────────────┼──────┼─────────────┼──────────────────────┼───────
Graph Schema Config        │  No  │     No      │  No                  │  No
Graph Entity Extractor     │  Yes │     No      │  No                  │  No
Entity Resolver            │  Opt │     Opt     │  No                  │  No
Graph Transformer          │  No  │     No      │  No                  │  No
Neo4j Graph Store          │  No  │     Yes     │  graph-rag (8004)    │  Yes
Graph Community Search     │  Yes │     No      │  graph-rag (8004)    │  Yes
Graph RAG Retriever        │  No  │     No      │  No                  │  No
```

---

## Canvas Wiring Example (Full Ingestion Pipeline)

```
[Documents] → [Graph Schema Config]
                        │
                        ▼ schema
[Documents] → [Graph Entity Extractor] ← [LLM Node]
                        │
                        ▼ entities
              [Entity Resolver]
                        │
                        ▼ resolved
              [Graph Transformer] ← [Graph Schema Config] (schema)
                        │
                        ▼ clean entities
              [Neo4j Graph Store] ← [Embedding Node]
                        │
                        ▼
              [Graph Community Search] ← [LLM Node]
```

## Canvas Wiring Example (Query Pipeline)

```
[User Query] → [Neo4j Graph Store (search mode)] ← [Embedding Node]
                        │
                        ▼ graph_results
              [Graph RAG Retriever]  ← [Pinecone Store (search)] (vector_results)
                        │
                        ▼ context
                   [LLM Node] → [Response]
```
