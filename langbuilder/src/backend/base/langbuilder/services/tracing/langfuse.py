from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger
from typing_extensions import override

from langbuilder.serialization.serialization import serialize
from langbuilder.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from langbuilder.graph.vertex.base import Vertex
    from langbuilder.services.tracing.schema import Log


class LangfuseCallbackWrapper:
    """Wrapper for Langfuse callback that suppresses 'parent run not found' and 'run not found' errors."""
    
    def __init__(self, callback):
        self._callback = callback
    
    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped callback."""
        attr = getattr(self._callback, name)
        
        # Wrap methods that might throw 'parent run not found', 'run not found', or KeyError for UUID errors
        if callable(attr) and name in (
            'on_tool_start', 'on_tool_end', 'on_tool_error',
            'on_chain_start', 'on_chain_end', 'on_chain_error',
            'on_llm_start', 'on_llm_end', 'on_llm_error'
        ):
            def wrapped_method(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except KeyError as e:
                    # Suppress UUID KeyError in Langfuse callback (run_id not found in self.runs)
                    logger.debug(f"Suppressed Langfuse KeyError in {name}: {e}")
                    return None
                except Exception as e:
                    # Suppress specific Langfuse tracing errors
                    error_msg = str(e).lower()
                    if 'parent run not found' in error_msg or 'run not found' in error_msg:
                        logger.debug(f"Suppressed Langfuse tracing error in {name}: {e}")
                        return None
                    raise
            return wrapped_method
        
        return attr


class LangFuseTracer(BaseTracer):
    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict = OrderedDict()  # spans that are not ended

        config = self._get_config()
        self._ready: bool = self.setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_langfuse(self, config) -> bool:
        try:
            from langfuse import Langfuse

            self._client = Langfuse(**config)
            try:
                from langfuse.api.core.request_options import RequestOptions

                self._client.client.health.health(request_options=RequestOptions(timeout_in_seconds=1))
            except Exception as e:  # noqa: BLE001
                logger.debug(f"can not connect to Langfuse: {e}")
                return False
            self.trace = self._client.trace(
                id=str(self.trace_id),
                name=self.flow_id,
                user_id=self.user_id,
                session_id=self.session_id,
            )

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up LangSmith tracer: {e}")
            return False

        return True

    @override
    def add_trace(
        self,
        trace_id: str,  # actualy component id
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        start_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        metadata_: dict = {"from_langbuilder_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        name = trace_name.removesuffix(f" ({trace_id})")
        content_span = {
            "name": name,
            "input": inputs,
            "metadata": metadata_,
            "start_time": start_time,
        }

        # if two component is built concurrently, will use wrong last span. just flatten now, maybe fix in future.
        # if len(self.spans) > 0:
        #     last_span = next(reversed(self.spans))
        #     span = self.spans[last_span].span(**content_span)
        # else:
        span = self.trace.span(**serialize(content_span))

        self.spans[trace_id] = span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        end_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span:
            output: dict = {}
            output |= outputs or {}
            output |= {"error": str(error)} if error else {}
            output |= {"logs": list(logs)} if logs else {}
            content = serialize({"output": output, "end_time": end_time})
            span.update(**content)

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._ready:
            return
        content_update = {
            "input": inputs,
            "output": outputs,
            "metadata": metadata,
        }
        self.trace.update(**serialize(content_update))

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        # get callback from parent span
        stateful_client = self.spans[next(reversed(self.spans))] if len(self.spans) > 0 else self.trace
        langfuse_callback = stateful_client.get_langchain_handler()
        
        # Wrap the callback to suppress 'parent run not found' and 'run not found' errors
        return LangfuseCallbackWrapper(langfuse_callback) if langfuse_callback else None

    @staticmethod
    def _get_config() -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_HOST", None)
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}
