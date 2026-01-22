"""Schema definitions for LangGraph adapter - independent from old graph folder."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, NamedTuple

from pydantic import BaseModel, Field, field_serializer, model_validator

from langbuilder.schema.schema import OutputValue, StreamURL
from langbuilder.serialization.serialization import serialize
from langbuilder.utils.schemas import ChatOutputResponse, ContainsEnumMeta

if TYPE_CHECKING:
    from langbuilder.graph_langgraph.vertex_wrapper import LangGraphVertex


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    """Types of interface components."""
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"
    DataOutput = "DataOutput"
    WebhookInput = "Webhook"


# Component type groupings
CHAT_COMPONENTS = [InterfaceComponentTypes.ChatInput, InterfaceComponentTypes.ChatOutput]
RECORDS_COMPONENTS = [InterfaceComponentTypes.DataOutput]
INPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatInput,
    InterfaceComponentTypes.WebhookInput,
    InterfaceComponentTypes.TextInput,
]
OUTPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatOutput,
    InterfaceComponentTypes.DataOutput,
    InterfaceComponentTypes.TextOutput,
]


class ResultData(BaseModel):
    """Result data from a single vertex/component execution."""
    results: Any | None = Field(default_factory=dict)
    artifacts: Any | None = Field(default_factory=dict)
    outputs: dict | None = Field(default_factory=dict)
    logs: dict | None = Field(default_factory=dict)
    messages: list[ChatOutputResponse] | None = Field(default_factory=list)
    timedelta: float | None = None
    duration: str | None = None
    component_display_name: str | None = None
    component_id: str | None = None
    used_frozen_result: bool | None = False

    @field_serializer("results")
    def serialize_results(self, value):
        if isinstance(value, dict):
            return {key: serialize(val) for key, val in value.items()}
        return serialize(value)

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values):
        if not values.get("outputs") and values.get("artifacts"):
            # Build the log from the artifacts
            for key in values["artifacts"]:
                message = values["artifacts"][key]
                if message is None:
                    continue
                if "stream_url" in message and "type" in message:
                    stream_url = StreamURL(location=message["stream_url"])
                    values["outputs"].update({key: OutputValue(message=stream_url, type=message["type"])})
                elif "type" in message:
                    values["outputs"].update({key: OutputValue(message=message, type=message["type"])})
        return values


class RunOutputs(BaseModel):
    """Output structure for a graph run - contains inputs and results.
    
    This is the return type of LangGraphAdapter.arun() method.
    Each run can have multiple outputs (one per output vertex).
    """
    inputs: dict = Field(default_factory=dict)
    outputs: list[ResultData | None] = Field(default_factory=list)


class VertexBuildResult(NamedTuple):
    """Result of building a single vertex."""
    result_dict: dict[str, Any]
    params: str
    valid: bool
    artifacts: dict[str, Any]
    vertex: LangGraphVertex

