from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import TYPE_CHECKING, Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger

from agentcore.services.base import Service
from agentcore.services.rabbitmq.config import RabbitMQConfig

if TYPE_CHECKING:
    from aio_pika import Channel, Connection, Queue
    from aio_pika.abc import AbstractRobustConnection


class RabbitMQService(Service):
    """RabbitMQ service for durable job scheduling with rate limiting.

    Option A implementation: consumers run inside the same FastAPI process.
    RabbitMQ provides durability, retry, rate-limiting (prefetch_count),
    and visibility (management UI). The asyncio.Queue + EventManager + SSE
    streaming stays completely unchanged.

    Queues:
        - agentcore.build : playground build jobs (POST /build/{id}/agent)
        - agentcore.run   : run/webhook jobs    (POST /run/{id})
    """

    name = "rabbitmq_service"

    def __init__(self) -> None:
        self.config = RabbitMQConfig()
        self._connection: AbstractRobustConnection | None = None
        self._channel: Channel | None = None
        self._build_queue: Queue | None = None
        self._run_queue: Queue | None = None
        self._consumer_tags: list[str] = []
        self._started = False
        self.ready = False

        # Stats tracking
        self._stats = {
            "build_published": 0,
            "build_completed": 0,
            "build_failed": 0,
            "run_published": 0,
            "run_completed": 0,
            "run_failed": 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to RabbitMQ, declare queues, and start consumers."""
        if not self.config.enabled:
            logger.info("RabbitMQ is disabled (RABBITMQ_ENABLED != true). Skipping.")
            return

        try:
            logger.info(f"Connecting to RabbitMQ at {self.config.host}:{self.config.port}")
            self._connection = await aio_pika.connect_robust(
                self.config.url,
                client_properties={"connection_name": "agentcore"},
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.config.prefetch_count)

            # Declare durable queues (survive broker restart)
            self._build_queue = await self._channel.declare_queue(
                self.config.build_queue,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": f"{self.config.build_queue}.dlq",
                },
            )
            self._run_queue = await self._channel.declare_queue(
                self.config.run_queue,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": f"{self.config.run_queue}.dlq",
                },
            )

            # Declare dead-letter queues
            await self._channel.declare_queue(f"{self.config.build_queue}.dlq", durable=True)
            await self._channel.declare_queue(f"{self.config.run_queue}.dlq", durable=True)

            # Start consumers
            tag1 = await self._build_queue.consume(self._on_build_message)
            tag2 = await self._run_queue.consume(self._on_run_message)
            self._consumer_tags = [tag1, tag2]

            self._started = True
            logger.info(
                f"RabbitMQ started: build_queue={self.config.build_queue}, "
                f"run_queue={self.config.run_queue}, prefetch={self.config.prefetch_count}"
            )
        except Exception:
            logger.exception("Failed to start RabbitMQ service")
            raise

    async def stop(self) -> None:
        """Gracefully close consumers and connection."""
        if not self._started:
            return

        try:
            if self._build_queue:
                await self._build_queue.cancel(self._consumer_tags[0] if self._consumer_tags else "")
            if self._run_queue and len(self._consumer_tags) > 1:
                await self._run_queue.cancel(self._consumer_tags[1])
        except Exception:
            logger.debug("Error cancelling RabbitMQ consumers (may already be closed)")

        try:
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
        except Exception:
            logger.debug("Error closing RabbitMQ connection (may already be closed)")

        self._started = False
        logger.info(f"RabbitMQ service stopped. Stats: {self._stats}")

    async def teardown(self) -> None:
        await self.stop()

    def is_enabled(self) -> bool:
        return self.config.enabled and self._started

    def get_stats(self) -> dict[str, int]:
        """Return message processing statistics."""
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_build_job(self, job_data: dict[str, Any]) -> str:
        """Publish a build job to the build queue."""
        result = await self._publish(self.config.build_queue, job_data)
        self._stats["build_published"] += 1
        return result

    async def publish_run_job(self, job_data: dict[str, Any]) -> str:
        """Publish a run job to the run queue."""
        result = await self._publish(self.config.run_queue, job_data)
        self._stats["run_published"] += 1
        return result

    async def _publish(self, queue_name: str, job_data: dict[str, Any]) -> str:
        """Publish a persistent message to the given queue."""
        if not self._channel or self._channel.is_closed:
            msg = "RabbitMQ channel is not available"
            raise RuntimeError(msg)

        message_id = job_data.get("job_id", str(uuid.uuid4()))
        body = json.dumps(job_data, default=str).encode("utf-8")

        message = aio_pika.Message(
            body=body,
            message_id=message_id,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={"retry_count": 0},
        )

        await self._channel.default_exchange.publish(
            message,
            routing_key=queue_name,
        )
        logger.debug(f"Published job {message_id} to {queue_name}")
        return message_id

    # ------------------------------------------------------------------
    # Consumers  (Option A: same process, access JobQueueService directly)
    # ------------------------------------------------------------------

    async def _retry_or_dlq(self, message: AbstractIncomingMessage, queue_name: str) -> None:
        """Republish a failed message with incremented retry_count, or reject to DLQ.

        RabbitMQ's requeue redelivers the SAME message with the SAME headers,
        so retry_count never increments. Instead, we ACK the original message
        and publish a NEW message with retry_count + 1. When max retries are
        exhausted, we REJECT the message (reject → dead-letter-exchange → DLQ).
        """
        retry_count = (message.headers or {}).get("retry_count", 0)
        next_retry = retry_count + 1

        # Use per-queue retry limit
        if queue_name == self.config.build_queue:
            max_retries = self.config.build_retry_max
        elif queue_name == self.config.run_queue:
            max_retries = self.config.run_retry_max
        else:
            max_retries = self.config.retry_max

        if next_retry > max_retries:
            # Exhausted retries — reject so it goes to DLQ
            logger.error(
                f"[RabbitMQ] Exhausted {max_retries} retries for {queue_name}, "
                f"sending to DLQ: {message.message_id}"
            )
            await message.reject(requeue=False)
            return

        # ACK the original and republish with incremented retry_count
        logger.warning(
            f"[RabbitMQ] Retrying {message.message_id} "
            f"(attempt {next_retry}/{self.config.retry_max})"
        )
        retry_message = aio_pika.Message(
            body=message.body,
            message_id=message.message_id,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={"retry_count": next_retry},
        )
        await message.ack()
        await self._channel.default_exchange.publish(
            retry_message,
            routing_key=queue_name,
        )

    async def _on_build_message(self, message: AbstractIncomingMessage) -> None:
        """Process a build job message from RabbitMQ.

        Build jobs (playground) start a task and WAIT for it to complete
        before ACKing. If the task fails, it is retried up to RETRY_MAX times.
        """
        job_id = None
        start_time = time.time()
        retry_count = (message.headers or {}).get("retry_count", 0)
        try:
            job_data = json.loads(message.body.decode("utf-8"))
            job_id = job_data["job_id"]
            logger.info(
                f"[RabbitMQ] Processing build job: {job_id} "
                f"(attempt {retry_count + 1})"
            )

            from agentcore.services.deps import get_queue_service

            queue_service = get_queue_service()
            _, event_manager, _, _ = queue_service.get_queue_data(job_id)

            # Execute and WAIT for the job to finish
            await self._execute_build_job(job_data, event_manager, queue_service)

            # Wait for the asyncio.Task to actually complete
            _, _, task, _ = queue_service.get_queue_data(job_id)
            if task and not task.done():
                await task

            elapsed = time.time() - start_time
            self._stats["build_completed"] += 1
            logger.info(
                f"[RabbitMQ] Build job completed: {job_id} "
                f"({elapsed:.2f}s)"
            )
            await message.ack()

        except Exception:
            elapsed = time.time() - start_time
            self._stats["build_failed"] += 1
            logger.exception(
                f"[RabbitMQ] Build job failed: {job_id} "
                f"(attempt {retry_count + 1}/{self.config.retry_max + 1}, "
                f"{elapsed:.2f}s)"
            )
            await self._retry_or_dlq(message, self.config.build_queue)

    async def _on_run_message(self, message: AbstractIncomingMessage) -> None:
        """Process a run job message from RabbitMQ.

        Run jobs execute the agent and WAIT for completion before ACKing.
        If the job fails, it is retried up to RETRY_MAX times.
        """
        job_id = None
        start_time = time.time()
        retry_count = (message.headers or {}).get("retry_count", 0)
        try:
            job_data = json.loads(message.body.decode("utf-8"))
            job_id = job_data["job_id"]
            logger.info(
                f"[RabbitMQ] Processing run job: {job_id} "
                f"(attempt {retry_count + 1})"
            )

            from agentcore.services.deps import get_queue_service

            queue_service = get_queue_service()
            _, event_manager, _, _ = queue_service.get_queue_data(job_id)

            await self._execute_run_job(job_data, event_manager, queue_service)

            elapsed = time.time() - start_time
            self._stats["run_completed"] += 1
            logger.info(
                f"[RabbitMQ] Run job completed: {job_id} "
                f"({elapsed:.2f}s)"
            )
            await message.ack()

        except Exception:
            elapsed = time.time() - start_time
            self._stats["run_failed"] += 1
            logger.exception(
                f"[RabbitMQ] Run job failed: {job_id} "
                f"(attempt {retry_count + 1}/{self.config.retry_max + 1}, "
                f"{elapsed:.2f}s)"
            )
            await self._retry_or_dlq(message, self.config.run_queue)

    async def _execute_build_job(
        self,
        job_data: dict[str, Any],
        event_manager: Any,
        queue_service: Any,
    ) -> None:
        """Execute a build job using the same logic as start_agent_build."""
        from fastapi import BackgroundTasks

        from agentcore.api.build import generate_agent_events
        from agentcore.api.v1_schemas import AgentDataRequest, InputValueRequest
        from agentcore.services.database.models.user.model import User
        from agentcore.services.deps import session_scope

        job_id = job_data["job_id"]
        agent_id = uuid.UUID(job_data["agent_id"])

        # Reconstruct inputs
        inputs = None
        if job_data.get("inputs"):
            inputs = InputValueRequest(**job_data["inputs"])

        # Reconstruct data
        data = None
        if job_data.get("data"):
            data = AgentDataRequest(**job_data["data"])

        # Reconstruct user
        user_id = job_data.get("user_id")
        async with session_scope() as session:
            current_user = await session.get(User, uuid.UUID(user_id)) if user_id else None

        if current_user is None:
            logger.error(f"[RabbitMQ] User not found for build job {job_id}")
            return

        background_tasks = BackgroundTasks()
        task_coro = generate_agent_events(
            agent_id=agent_id,
            background_tasks=background_tasks,
            event_manager=event_manager,
            inputs=inputs,
            data=data,
            files=job_data.get("files"),
            stop_component_id=job_data.get("stop_component_id"),
            start_component_id=job_data.get("start_component_id"),
            log_builds=job_data.get("log_builds", True),
            current_user=current_user,
            agent_name=job_data.get("agent_name"),
        )

        # Start the job through JobQueueService (creates asyncio.Task)
        queue_service.start_job(job_id, task_coro)

    async def _execute_run_job(
        self,
        job_data: dict[str, Any],
        event_manager: Any,
        queue_service: Any,
    ) -> None:
        """Execute a run job using the same logic as simplified_run_agent."""
        from agentcore.api.endpoints import run_agent_generator
        from agentcore.api.v1_schemas import SimplifiedAPIRequest
        from agentcore.services.database.models.agent.model import Agent
        from agentcore.services.deps import session_scope

        job_id = job_data["job_id"]
        agent_id = uuid.UUID(job_data["agent_id"])

        # Load agent from database
        async with session_scope() as session:
            agent = await session.get(Agent, agent_id)

        if agent is None:
            logger.error(f"[RabbitMQ] Agent not found for run job {job_id}")
            return

        # Apply resolved data if provided
        if job_data.get("agent_data"):
            agent.data = job_data["agent_data"]

        # Reconstruct input request
        input_request = SimplifiedAPIRequest(**job_data.get("input_request", {}))

        # Reconstruct deployment records
        prod_deployment = None
        uat_deployment = None
        if job_data.get("prod_deployment_id"):
            from agentcore.services.database.models.agent_deployment_prod.model import AgentDeploymentProd
            async with session_scope() as session:
                prod_deployment = await session.get(
                    AgentDeploymentProd, uuid.UUID(job_data["prod_deployment_id"])
                )
        if job_data.get("uat_deployment_id"):
            from agentcore.services.database.models.agent_deployment_uat.model import AgentDeploymentUAT
            async with session_scope() as session:
                uat_deployment = await session.get(
                    AgentDeploymentUAT, uuid.UUID(job_data["uat_deployment_id"])
                )

        client_consumed_queue = asyncio.Queue()

        await run_agent_generator(
            agent=agent,
            input_request=input_request,
            api_key_user=None,
            event_manager=event_manager,
            client_consumed_queue=client_consumed_queue,
            prod_deployment=prod_deployment,
            uat_deployment=uat_deployment,
        )
