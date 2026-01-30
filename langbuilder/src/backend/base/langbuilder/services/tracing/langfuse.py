from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger
from typing_extensions import override
from langchain.callbacks.base import BaseCallbackHandler
from langbuilder.serialization.serialization import serialize
from langbuilder.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langbuilder.graph.vertex.base import Vertex
    from langbuilder.services.tracing.schema import Log


class LangfuseCallbackWrapper(BaseCallbackHandler):
    """Wrapper for Langfuse callback that suppresses 'parent run not found' and 'run not found' errors.
    
    Inherits from BaseCallbackHandler to pass Pydantic validation in LangChain tools.
    We must explicitly override callback methods because __getattr__ is not called
    for methods that exist on the parent class (BaseCallbackHandler).
    """
    
    def __init__(self, callback):
        super().__init__()
        self._callback = callback
    
    def _safe_call(self, method_name: str, *args, **kwargs):
        """Safely call a method on the wrapped callback, suppressing known Langfuse errors."""
        try:
            method = getattr(self._callback, method_name, None)
            if method:
                return method(*args, **kwargs)
        except KeyError as e:
            # Suppress UUID KeyError in Langfuse callback (run_id not found in self.runs)
            logger.debug(f"Suppressed Langfuse KeyError in {method_name}: {e}")
        except Exception as e:
            # Suppress specific Langfuse tracing errors
            error_msg = str(e).lower()
            if 'parent run not found' in error_msg or 'run not found' in error_msg:
                logger.debug(f"Suppressed Langfuse tracing error in {method_name}: {e}")
            else:
                raise
        return None

    # LLM callbacks - required for token/model tracing
    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        return self._safe_call('on_llm_start', serialized, prompts, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    def on_llm_new_token(self, token, *, chunk=None, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_llm_new_token', token, chunk=chunk, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def on_llm_end(self, response, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_llm_end', response, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def on_llm_error(self, error, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_llm_error', error, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    # Chat model callbacks
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        return self._safe_call('on_chat_model_start', serialized, messages, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    # Chain callbacks
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        return self._safe_call('on_chain_start', serialized, inputs, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_chain_end', outputs, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def on_chain_error(self, error, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_chain_error', error, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    # Tool callbacks
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        return self._safe_call('on_tool_start', serialized, input_str, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_tool_end', output, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def on_tool_error(self, error, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_tool_error', error, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    # Retriever callbacks
    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        return self._safe_call('on_retriever_start', serialized, query, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    def on_retriever_end(self, documents, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_retriever_end', documents, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def on_retriever_error(self, error, *, run_id, parent_run_id=None, tags=None, **kwargs):
        return self._safe_call('on_retriever_error', error, run_id=run_id, parent_run_id=parent_run_id, tags=tags, **kwargs)

    def __getattr__(self, name):
        """Delegate any other attribute access to the wrapped callback."""
        return getattr(self._callback, name)


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
