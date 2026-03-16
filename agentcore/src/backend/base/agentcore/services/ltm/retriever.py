"""LTM Retriever.

Retrieves long-term memory context from Pinecone (semantic summaries)
and/or Neo4j (entity/relationship graph) using direct connections.
"""

from __future__ import annotations

from loguru import logger


async def _embed_query(query: str) -> list[float]:
    """Generate embedding using the configured provider (OpenAI or Azure OpenAI)."""
    from agentcore.services.ltm.embeddings import embed_single
    return await embed_single(query)


async def retrieve_from_pinecone(query: str, agent_id: str, top_k: int = 5, env: str = "Dev") -> list[str]:
    """Retrieve relevant conversation summaries from Pinecone."""
    from agentcore.services.deps import get_settings_service

    settings = get_settings_service().settings
    if not settings.ltm_pinecone_api_key:
        logger.debug("[LTM] LTM_PINECONE_API_KEY not configured, skipping Pinecone retrieval")
        return []

    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.ltm_pinecone_api_key)
        index_name = settings.ltm_pinecone_index

        existing = [idx.name for idx in pc.list_indexes()]
        if index_name not in existing:
            logger.debug(f"[LTM] Pinecone index={index_name} does not exist yet")
            return []

        index = pc.Index(index_name)
        query_embedding = await _embed_query(query)
        if not query_embedding:
            return []

        # Namespace by environment — each agent+env combo is fully isolated
        env_suffix = f"_{env.lower()}" if env != "Dev" else ""
        namespace = f"{agent_id}{env_suffix}"

        logger.info(f"[LTM] Pinecone query: namespace={namespace}, top_k={top_k}")

        results = index.query(
            namespace=namespace,
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            # Extra safety: filter by agent_id in metadata
            filter={"agent_id": {"$eq": agent_id}},
        )

        summaries = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            text = meta.get("summary", "")
            score = match.get("score", 0)
            stored_agent = meta.get("agent_id", "?")
            if text:
                summaries.append(text)
                logger.debug(f"[LTM] Pinecone match: score={score:.3f}, agent={stored_agent}")

        logger.info(f"[LTM] === PINECONE RETRIEVAL ===")
        logger.info(f"[LTM] Pinecone namespace={namespace}, retrieved {len(summaries)} summaries for agent={agent_id}")
        for i, s in enumerate(summaries):
            logger.info(f"[LTM]   Pinecone[{i}]: {s[:200]}...")
        logger.info(f"[LTM] === END PINECONE RETRIEVAL ===")
        return summaries
    except Exception as e:
        logger.error(f"[LTM] Pinecone retrieval failed: {e}")
        return []


async def retrieve_from_neo4j(query: str, agent_id: str, top_k: int = 5, env: str = "Dev") -> list[str]:
    """Retrieve relevant facts/entities from Neo4j graph."""
    from agentcore.services.deps import get_settings_service

    settings = get_settings_service().settings
    if not settings.ltm_neo4j_uri:
        logger.debug("[LTM] LTM_NEO4J_URI not configured, skipping Neo4j retrieval")
        return []

    # Namespace by environment
    env_suffix = f"_{env.lower()}" if env != "Dev" else ""
    graph_kb_id = f"{settings.ltm_neo4j_graph_kb_id}_{agent_id}{env_suffix}"

    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.ltm_neo4j_uri,
            auth=(settings.ltm_neo4j_username, settings.ltm_neo4j_password),
        )

        keywords = [w.lower() for w in query.split() if len(w) > 3]
        facts = []

        logger.info(f"[LTM] Neo4j query: graph_kb_id={graph_kb_id}, keywords={keywords[:5]}")

        with driver.session(database=settings.ltm_neo4j_database) as session:
            for keyword in keywords[:5]:
                result = session.run(
                    "MATCH (e:__Entity__ {graph_kb_id: $graph_kb_id}) "
                    "WHERE toLower(e.name) CONTAINS $keyword "
                    "   OR toLower(e.description) CONTAINS $keyword "
                    "OPTIONAL MATCH (e)-[r:RELATED_TO]-(neighbor:__Entity__ {graph_kb_id: $graph_kb_id}) "
                    "RETURN e.name AS name, e.type AS type, e.description AS description, "
                    "       collect(DISTINCT {name: neighbor.name, rel: r.type}) AS neighbors "
                    "LIMIT $top_k",
                    keyword=keyword, graph_kb_id=graph_kb_id, top_k=top_k,
                )

                for record in result:
                    name = record["name"]
                    desc = record["description"] or ""
                    etype = record["type"] or ""
                    fact = f"{name} ({etype}): {desc}" if desc else f"{name} ({etype})"
                    if fact not in facts:
                        facts.append(fact)
                    for neighbor in record["neighbors"] or []:
                        n_name = neighbor.get("name", "")
                        if n_name:
                            rel_fact = f"{name} --[{neighbor.get('rel', 'RELATED_TO')}]--> {n_name}"
                            if rel_fact not in facts:
                                facts.append(rel_fact)

        driver.close()
        logger.info(f"[LTM] === NEO4J RETRIEVAL ===")
        logger.info(f"[LTM] Neo4j retrieved {len(facts)} facts for agent={agent_id}")
        for i, f in enumerate(facts[:top_k * 3]):
            logger.info(f"[LTM]   Neo4j[{i}]: {f}")
        logger.info(f"[LTM] === END NEO4J RETRIEVAL ===")
        return facts[:top_k * 3]
    except Exception as e:
        logger.error(f"[LTM] Neo4j retrieval failed: {e}")
        return []


async def _detect_environment(agent_id: str) -> str:
    """Detect which environment has conversations for this agent.

    Checks orch_conversation first (deployed agents), then dev.
    For orch, resolves PROD vs UAT via deployment_id lookup.
    """
    from sqlmodel import select
    from agentcore.services.deps import session_scope
    from uuid import UUID

    agent_uuid = UUID(agent_id)

    # 1. Check orch_conversation (deployed agents — both UAT & PROD)
    try:
        from agentcore.services.database.models.orch_conversation.model import OrchConversationTable

        async with session_scope() as session:
            stmt = (
                select(OrchConversationTable.deployment_id)
                .where(OrchConversationTable.agent_id == agent_uuid)
                .where(OrchConversationTable.deployment_id.isnot(None))
                .limit(1)
            )
            result = await session.exec(stmt)
            deployment_id = result.first()

            if deployment_id:
                # Resolve PROD vs UAT from deployment_id
                try:
                    from agentcore.services.database.models.agent_deployment_prod.model import AgentDeploymentProd
                    prod = await session.get(AgentDeploymentProd, deployment_id)
                    if prod:
                        return "PROD"
                except Exception:
                    pass
                try:
                    from agentcore.services.database.models.agent_deployment_uat.model import AgentDeploymentUAT
                    uat = await session.get(AgentDeploymentUAT, deployment_id)
                    if uat:
                        return "UAT"
                except Exception:
                    pass
                return "Orchestrator"
    except Exception:
        pass

    return "Dev"


async def retrieve(
    query: str,
    agent_id: str,
    mode: str = "Both",
    pinecone_top_k: int = 5,
    neo4j_top_k: int = 10,
    # Legacy parameter for backward compatibility
    top_k: int | None = None,
    env: str | None = None,
) -> str:
    """Main retrieval entry point.

    Automatically detects environment (PROD/UAT/Orchestrator/Dev) and queries
    the correct namespace.

    Args:
        query: Current user query.
        agent_id: The agent ID.
        mode: "Pinecone Only", "Neo4j Only", or "Both".
        pinecone_top_k: Number of summaries to retrieve from Pinecone.
        neo4j_top_k: Number of entities/relationships from Neo4j.
        top_k: Legacy param — if set, used for both pinecone_top_k and neo4j_top_k.
        env: Optional environment override. If None, auto-detected.

    Returns:
        Formatted LTM context string.
    """
    if top_k is not None:
        pinecone_top_k = top_k
        neo4j_top_k = top_k

    # Use provided env or detect from conversation tables
    if not env:
        env = await _detect_environment(agent_id)
    logger.info(f"[LTM] Retrieval environment={env} for agent={agent_id}")

    parts = []

    if mode in ("Pinecone Only", "Both"):
        summaries = await retrieve_from_pinecone(query, agent_id, pinecone_top_k, env=env)
        if summaries:
            parts.append("Relevant Past Conversations:\n" + "\n".join(f"- {s}" for s in summaries))

    if mode in ("Neo4j Only", "Both"):
        facts = await retrieve_from_neo4j(query, agent_id, neo4j_top_k, env=env)
        if facts:
            parts.append("Known Facts & Relationships:\n" + "\n".join(f"- {f}" for f in facts))

    result = "\n\n".join(parts) if parts else ""
    if result:
        logger.info(f"[LTM] === FINAL LTM CONTEXT ({len(result)} chars) ===\n{result}\n=== END LTM CONTEXT ===")
    return result
