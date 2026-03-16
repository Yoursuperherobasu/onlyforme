"""LTM Background Processor Service.

Manages the Long Term Memory pipeline using in-memory tracking + Redis cache:
1. Tracks message counts per agent_id (in-memory dict + Redis for persistence)
2. Marks agents as "ready for processing" after N messages OR time interval
3. Actual processing happens inline when the Memory component runs with a connected LLM
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from loguru import logger

from agentcore.services.base import Service

# Redis key prefixes for LTM state
LTM_COUNT_PREFIX = "ltm:msg_count:"
LTM_LAST_PROCESSED_PREFIX = "ltm:last_processed:"


class LTMService(Service):
    """Service that tracks conversation activity and processes LTM inline.

    The LLM for summarization/fact extraction always comes from the agent's flow
    (connected via HandleInput on the Memory component). This service only:
    - Tracks message counts per agent_id (in-memory + Redis)
    - Checks if threshold is reached
    - Runs the pipeline when called with an LLM by the Memory component
    """

    name = "ltm_service"

    def __init__(self) -> None:
        self._scheduler = None
        self._started = False
        self._agents_in_progress: set[str] = set()
        # In-memory fallback when Redis is unavailable
        self._message_counts: dict[str, int] = defaultdict(int)
        self._last_processed: dict[str, datetime] = {}

    def _get_redis(self):
        """Get Redis client if available."""
        try:
            from agentcore.services.deps import get_settings_service
            from agentcore.services.cache.redis_client import get_redis_client

            settings_service = get_settings_service()
            if settings_service.settings.cache_type == "redis":
                return get_redis_client(settings_service)
        except Exception:
            pass
        return None

    def _ensure_scheduler(self):
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                self._scheduler = AsyncIOScheduler()
            except ImportError:
                logger.warning("[LTM] APScheduler not installed. Time-based LTM triggers disabled.")

    def start(self) -> None:
        """Start the LTM service."""
        from agentcore.services.deps import get_settings_service

        settings = get_settings_service().settings
        if not settings.ltm_enabled:
            logger.info("[LTM] Service disabled (LTM_ENABLED=False)")
            self.set_ready()
            return

        self._ensure_scheduler()
        if self._scheduler and not self._started:
            interval_minutes = settings.ltm_time_interval_minutes
            self._scheduler.add_job(
                self._time_based_sweep,
                "interval",
                minutes=interval_minutes,
                id="ltm_time_sweep",
                replace_existing=True,
            )
            self._scheduler.start()
            self._started = True
            logger.info(
                f"[LTM] Service started | threshold={settings.ltm_message_threshold} msgs | "
                f"interval={interval_minutes} min"
            )
        self.set_ready()

    async def teardown(self) -> None:
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("[LTM] Service shut down")

    async def on_message_stored(self, agent_id: str | UUID, session_id: str | None = None) -> None:
        """Called by ChatOutput after storing a message. Increments the message counter."""
        from agentcore.services.deps import get_settings_service

        settings = get_settings_service().settings
        if not settings.ltm_enabled:
            return

        agent_id_str = str(agent_id)

        try:
            # Try Redis first, fall back to in-memory
            redis = self._get_redis()
            if redis:
                key = f"{LTM_COUNT_PREFIX}{agent_id_str}"
                count = await redis.incr(key)
                # Set TTL of 24h so keys don't accumulate forever
                await redis.expire(key, 86400)
            else:
                self._message_counts[agent_id_str] += 1
                count = self._message_counts[agent_id_str]

            logger.info(f"[LTM] Message count for agent={agent_id_str}: {count}/{settings.ltm_message_threshold}")
        except Exception as e:
            # Fallback to in-memory
            self._message_counts[agent_id_str] += 1
            logger.debug(f"[LTM] on_message_stored (in-memory fallback): {e}")

    async def _time_based_sweep(self) -> None:
        """Periodic sweep: log agents with pending messages."""
        try:
            redis = self._get_redis()
            if redis:
                count = 0
                async for key in redis.scan_iter(match=f"{LTM_COUNT_PREFIX}*", count=100):
                    val = await redis.get(key)
                    if val and int(val) > 0:
                        count += 1
                if count:
                    logger.info(f"[LTM] Time sweep: {count} agents have pending messages")
            elif self._message_counts:
                pending = sum(1 for c in self._message_counts.values() if c > 0)
                if pending:
                    logger.info(f"[LTM] Time sweep: {pending} agents have pending messages (in-memory)")
        except Exception as e:
            logger.debug(f"[LTM] Time-based sweep failed: {e}")

    async def should_process(self, agent_id: str) -> bool:
        """Check if an agent has enough pending messages to trigger LTM processing."""
        from agentcore.services.deps import get_settings_service

        settings = get_settings_service().settings
        if not settings.ltm_enabled:
            return False

        try:
            redis = self._get_redis()
            if redis:
                key = f"{LTM_COUNT_PREFIX}{agent_id}"
                val = await redis.get(key)
                count = int(val) if val else 0
            else:
                count = self._message_counts.get(agent_id, 0)

            return count >= settings.ltm_message_threshold
        except Exception:
            return self._message_counts.get(agent_id, 0) >= settings.ltm_message_threshold

    async def process_with_llm(self, agent_id: str, llm=None) -> None:
        """Run the LTM pipeline.

        Uses the provided LLM or creates one from LTM settings (LTM_LLM_PROVIDER/MODEL).

        Pipeline:
        1. Fetch recent messages (since last processed)
        2. Summarize via LLM
        3. Extract facts/entities via LLM
        4. Store entities to Neo4j
        5. Store summary embedding to Pinecone
        6. Reset counter
        """
        logger.info(f"[LTM] process_with_llm called for agent={agent_id}")
        if agent_id in self._agents_in_progress:
            logger.info(f"[LTM] Skipping — agent {agent_id} already in progress")
            return

        if not await self.should_process(agent_id):
            logger.info(f"[LTM] Skipping — should_process returned False (2nd check)")
            return

        self._agents_in_progress.add(agent_id)
        try:
            messages, env = await self._get_recent_messages(agent_id)
            if not messages:
                logger.info(f"[LTM] No recent messages found for agent={agent_id}, resetting counter and last_processed")
                # Reset so next time it fetches all messages
                await self._reset_counter(agent_id)
                # Clear last_processed so all messages are considered "new"
                try:
                    redis = self._get_redis()
                    if redis:
                        await redis.delete(f"{LTM_LAST_PROCESSED_PREFIX}{agent_id}")
                    self._last_processed.pop(agent_id, None)
                except Exception:
                    pass
                return

            logger.info(f"[LTM] Processing {len(messages)} messages for agent={agent_id} (env={env})")

            # 2. Summarize (uses settings LLM if none passed)
            from agentcore.services.deps import get_settings_service
            max_summary_tokens = get_settings_service().settings.ltm_max_summary_tokens or 500
            from agentcore.services.ltm.summarizer import summarize_conversation
            summary = await summarize_conversation(messages, llm, max_tokens=max_summary_tokens)
            if not summary:
                return

            # 3. Extract facts (uses settings LLM if none passed)
            from agentcore.services.ltm.fact_extractor import extract_facts
            facts = await extract_facts(summary, llm)

            # 4. Store to Neo4j (namespaced by environment)
            await self._store_to_neo4j(agent_id, facts, env=env)

            # 5. Store summary to Pinecone (namespaced by environment)
            await self._store_to_pinecone(agent_id, summary, env=env)

            # 6. Reset counter and update last_processed
            await self._reset_counter(agent_id)

            logger.info(f"[LTM] ========== PIPELINE COMPLETED for agent={agent_id} ==========")
        except Exception as e:
            logger.error(f"[LTM] Pipeline failed for agent={agent_id}: {e}")
        finally:
            self._agents_in_progress.discard(agent_id)

    async def _get_recent_messages(self, agent_id: str) -> tuple[list, str]:
        """Fetch messages since the last LTM processing.

        Checks tables in priority order: PROD → UAT → Orchestrator → Dev.
        Returns (messages, environment_name).
        """
        # Get last processed timestamp
        last_ts = None
        try:
            redis = self._get_redis()
            if redis:
                key = f"{LTM_LAST_PROCESSED_PREFIX}{agent_id}"
                val = await redis.get(key)
                if val:
                    last_ts = datetime.fromisoformat(val.decode() if isinstance(val, bytes) else val)
            else:
                last_ts = self._last_processed.get(agent_id)
        except Exception:
            last_ts = self._last_processed.get(agent_id)

        # Query messages with environment-aware priority
        all_messages, env = await self._query_messages_by_priority(agent_id)

        if last_ts and all_messages:
            def _parse_ts(ts):
                if ts is None:
                    return None
                if isinstance(ts, datetime):
                    return ts.replace(tzinfo=None) if ts.tzinfo else ts
                if isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts)
                        return dt.replace(tzinfo=None) if dt.tzinfo else dt
                    except (ValueError, TypeError):
                        return None
                return None

            last_ts_naive = _parse_ts(last_ts)
            if last_ts_naive:
                all_messages = [
                    m for m in all_messages
                    if _parse_ts(m.timestamp) and _parse_ts(m.timestamp) > last_ts_naive
                ]

        return all_messages, env

    async def _query_messages_by_priority(self, agent_id: str) -> tuple[list, str]:
        """Query messages from orch_conversation first, then dev conversation.

        For orch_conversation, resolves environment (PROD/UAT) by checking
        the deployment_id against AgentDeploymentProd/AgentDeploymentUAT tables.

        Priority:
          1. orch_conversation (deployed agents — both UAT & PROD)
          2. conversation (dev/playground — fallback)

        Returns (messages, environment_name).
        """
        from sqlmodel import col, select
        from agentcore.services.deps import session_scope
        from agentcore.schema.message import Message

        agent_uuid = UUID(agent_id)

        # 1. Check orch_conversation first (all deployed agents)
        try:
            from agentcore.services.database.models.orch_conversation.model import OrchConversationTable

            async with session_scope() as session:
                stmt = (
                    select(OrchConversationTable)
                    .where(OrchConversationTable.agent_id == agent_uuid)
                    .where(OrchConversationTable.error == False)  # noqa: E712
                    .order_by(col(OrchConversationTable.timestamp).asc())
                    .limit(1000)
                )
                results = await session.exec(stmt)
                rows = list(results.all())

                if rows:
                    # Resolve environment from deployment_id
                    env = await self._resolve_orch_environment(rows, session)
                    logger.info(
                        f"[LTM] Found {len(rows)} messages in orch_conversation "
                        f"(env={env}) for agent={agent_id}"
                    )
                    return [
                        await Message.create(**r.model_dump())
                        for r in rows
                    ], env
        except Exception as e:
            logger.debug(f"[LTM] Skipping orch_conversation: {e}")

        # 2. Check conversation_prod table (PROD deployed agents)
        try:
            from agentcore.services.database.models.conversation_prod.model import ConversationProdTable

            async with session_scope() as session:
                stmt = (
                    select(ConversationProdTable)
                    .where(ConversationProdTable.agent_id == agent_uuid)
                    .where(ConversationProdTable.error == False)  # noqa: E712
                    .order_by(col(ConversationProdTable.timestamp).asc())
                    .limit(1000)
                )
                results = await session.exec(stmt)
                rows = list(results.all())

                if rows:
                    logger.info(
                        f"[LTM] Found {len(rows)} messages in conversation_prod (PROD) "
                        f"for agent={agent_id}"
                    )
                    return [
                        await Message.create(**r.model_dump())
                        for r in rows
                    ], "PROD"
        except Exception as e:
            logger.debug(f"[LTM] Skipping conversation_prod: {e}")

        # 3. Check conversation_uat table (UAT deployed agents)
        try:
            from agentcore.services.database.models.conversation_uat.model import ConversationUATTable

            async with session_scope() as session:
                stmt = (
                    select(ConversationUATTable)
                    .where(ConversationUATTable.agent_id == agent_uuid)
                    .where(ConversationUATTable.error == False)  # noqa: E712
                    .order_by(col(ConversationUATTable.timestamp).asc())
                    .limit(1000)
                )
                results = await session.exec(stmt)
                rows = list(results.all())

                if rows:
                    logger.info(
                        f"[LTM] Found {len(rows)} messages in conversation_uat (UAT) "
                        f"for agent={agent_id}"
                    )
                    return [
                        await Message.create(**r.model_dump())
                        for r in rows
                    ], "UAT"
        except Exception as e:
            logger.debug(f"[LTM] Skipping conversation_uat: {e}")

        # 4. Fallback to dev conversation table
        try:
            from agentcore.services.database.models.conversation.model import ConversationTable

            async with session_scope() as session:
                stmt = (
                    select(ConversationTable)
                    .where(ConversationTable.agent_id == agent_uuid)
                    .where(ConversationTable.error == False)  # noqa: E712
                    .order_by(col(ConversationTable.timestamp).asc())
                    .limit(1000)
                )
                results = await session.exec(stmt)
                rows = list(results.all())

                if rows:
                    logger.info(
                        f"[LTM] Found {len(rows)} messages in conversation (Dev) "
                        f"for agent={agent_id}"
                    )
                    return [
                        await Message.create(**r.model_dump())
                        for r in rows
                    ], "Dev"
        except Exception as e:
            logger.debug(f"[LTM] Skipping conversation: {e}")

        return [], "Dev"

    async def _resolve_orch_environment(self, rows: list, session) -> str:
        """Resolve PROD vs UAT from orch_conversation deployment_id.

        Checks the first row's deployment_id against AgentDeploymentProd first,
        then AgentDeploymentUAT. Falls back to 'Orchestrator'.
        """
        # Find the first row with a deployment_id
        deployment_id = None
        for row in rows:
            did = getattr(row, "deployment_id", None)
            if did:
                deployment_id = did
                break

        if not deployment_id:
            return "Orchestrator"

        # Check PROD first
        try:
            from agentcore.services.database.models.agent_deployment_prod.model import AgentDeploymentProd
            prod = await session.get(AgentDeploymentProd, deployment_id)
            if prod:
                return "PROD"
        except Exception:
            pass

        # Check UAT
        try:
            from agentcore.services.database.models.agent_deployment_uat.model import AgentDeploymentUAT
            uat = await session.get(AgentDeploymentUAT, deployment_id)
            if uat:
                return "UAT"
        except Exception:
            pass

        return "Orchestrator"

    async def _reset_counter(self, agent_id: str) -> None:
        """Reset message counter and update last_processed timestamp."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        try:
            redis = self._get_redis()
            if redis:
                await redis.set(f"{LTM_COUNT_PREFIX}{agent_id}", 0)
                await redis.set(f"{LTM_LAST_PROCESSED_PREFIX}{agent_id}", now_str)
                await redis.expire(f"{LTM_LAST_PROCESSED_PREFIX}{agent_id}", 86400 * 30)  # 30 days
            else:
                self._message_counts[agent_id] = 0
                self._last_processed[agent_id] = now
        except Exception:
            self._message_counts[agent_id] = 0
            self._last_processed[agent_id] = now

    async def _store_to_neo4j(self, agent_id: str, facts: dict, env: str = "Dev") -> None:
        """Store extracted entities and relationships to Neo4j (direct connection).

        Namespaces data by environment so PROD/UAT/Dev data stays separate.
        """
        from agentcore.services.deps import get_settings_service

        settings = get_settings_service().settings
        if not settings.ltm_neo4j_uri:
            logger.debug("[LTM] LTM_NEO4J_URI not configured, skipping Neo4j storage")
            return

        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])
        if not entities:
            return

        # Namespace by environment: ltm_{agent_id}_prod, ltm_{agent_id}_uat, ltm_{agent_id}
        env_suffix = f"_{env.lower()}" if env != "Dev" else ""
        graph_kb_id = f"{settings.ltm_neo4j_graph_kb_id}_{agent_id}{env_suffix}"

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                settings.ltm_neo4j_uri,
                auth=(settings.ltm_neo4j_username, settings.ltm_neo4j_password),
            )

            with driver.session(database=settings.ltm_neo4j_database) as session:
                for entity in entities:
                    session.run(
                        "MERGE (e:__Entity__ {name: $name, graph_kb_id: $graph_kb_id}) "
                        "SET e.type = $type, e.description = $description",
                        name=entity.get("name", ""),
                        type=entity.get("type", "CONCEPT"),
                        description=entity.get("description", ""),
                        graph_kb_id=graph_kb_id,
                    )

                for rel in relationships:
                    session.run(
                        "MATCH (a:__Entity__ {name: $source, graph_kb_id: $graph_kb_id}) "
                        "MATCH (b:__Entity__ {name: $target, graph_kb_id: $graph_kb_id}) "
                        "MERGE (a)-[r:RELATED_TO]->(b) "
                        "SET r.type = $rel_type, r.description = $description, r.weight = $weight",
                        source=rel.get("source", ""),
                        target=rel.get("target", ""),
                        rel_type=rel.get("type", "RELATED_TO"),
                        description=rel.get("description", ""),
                        weight=rel.get("weight", 0.5),
                        graph_kb_id=graph_kb_id,
                    )

            driver.close()
            logger.info(f"[LTM] === NEO4J STORAGE ===")
            logger.info(f"[LTM] Stored {len(entities)} entities + {len(relationships)} rels to Neo4j (graph_kb_id={graph_kb_id})")
            for e in entities:
                logger.info(f"[LTM]   Neo4j Entity: {e.get('name')} ({e.get('type')})")
            for r in relationships:
                logger.info(f"[LTM]   Neo4j Rel: {r.get('source')} --[{r.get('type')}]--> {r.get('target')}")
            logger.info(f"[LTM] === END NEO4J ===")
        except Exception as e:
            logger.error(f"[LTM] Neo4j ingestion failed for agent={agent_id}: {e}")

    async def _store_to_pinecone(self, agent_id: str, summary: str, env: str = "Dev") -> None:
        """Store conversation summary embedding to Pinecone (direct connection).

        Namespaces data by environment so PROD/UAT/Dev data stays separate.
        """
        from agentcore.services.deps import get_settings_service

        settings = get_settings_service().settings
        if not settings.ltm_pinecone_api_key:
            logger.debug("[LTM] LTM_PINECONE_API_KEY not configured, skipping Pinecone storage")
            return

        try:
            from pinecone import Pinecone, ServerlessSpec
            import hashlib

            pc = Pinecone(api_key=settings.ltm_pinecone_api_key)
            index_name = settings.ltm_pinecone_index

            existing = [idx.name for idx in pc.list_indexes()]
            if index_name not in existing:
                sample = await self._embed_text("test")
                dimension = len(sample)
                pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=settings.ltm_pinecone_cloud,
                        region=settings.ltm_pinecone_region,
                    ),
                )
                logger.info(f"[LTM] Created Pinecone index={index_name} dim={dimension}")

            index = pc.Index(index_name)

            embedding = await self._embed_text(summary)

            vec_id = hashlib.sha256(summary.encode()).hexdigest()[:16]
            timestamp = datetime.now(timezone.utc).isoformat()

            # Namespace by environment: {agent_id}_prod, {agent_id}_uat, {agent_id}
            env_suffix = f"_{env.lower()}" if env != "Dev" else ""
            namespace = f"{agent_id}{env_suffix}"

            index.upsert(
                vectors=[{
                    "id": vec_id,
                    "values": embedding,
                    "metadata": {
                        "summary": summary[:40000],
                        "agent_id": agent_id,
                        "environment": env,
                        "timestamp": timestamp,
                    },
                }],
                namespace=namespace,
            )
            logger.info(f"[LTM] === PINECONE STORAGE ===")
            logger.info(f"[LTM] Stored summary to Pinecone index={index_name}, namespace={namespace}, vec_id={vec_id}")
            logger.info(f"[LTM] Summary preview: {summary[:200]}...")
            logger.info(f"[LTM] Embedding dimension: {len(embedding)}")
            logger.info(f"[LTM] === END PINECONE ===")
        except Exception as e:
            logger.error(f"[LTM] Pinecone ingestion failed for agent={agent_id}: {e}")

    async def _embed_text(self, text: str) -> list[float]:
        """Generate embedding using the configured provider (OpenAI or Azure OpenAI)."""
        from agentcore.services.ltm.embeddings import embed_single
        return await embed_single(text)

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using the configured provider."""
        from agentcore.services.ltm.embeddings import embed_batch
        return await embed_batch(texts)
