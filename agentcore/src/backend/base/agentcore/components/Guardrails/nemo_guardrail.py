import asyncio
import concurrent.futures

from sqlmodel import select

from agentcore.custom.custom_node.node import Node
from agentcore.inputs.inputs import BoolInput, MessageTextInput, MultilineInput
from agentcore.io import DropdownInput, Output
from agentcore.schema.message import Message
from agentcore.services.database.models.guardrail_catalogue.model import GuardrailCatalogue
from agentcore.services.deps import session_scope
from agentcore.services.guardrails import apply_nemo_guardrail_text, is_nemo_runtime_config_ready


def _run_async(coro):
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)


def _fetch_active_guardrail_options() -> list[str]:
    async def _query() -> list[str]:
        async with session_scope() as session:
            stmt = (
                select(GuardrailCatalogue)
                .where(GuardrailCatalogue.status == "active")
                .order_by(GuardrailCatalogue.name.asc())
            )
            rows = (await session.exec(stmt)).all()
            ready_rows = [row for row in rows if is_nemo_runtime_config_ready(row.runtime_config)]
            return [f"{row.name} | {row.id}" for row in ready_rows]

    try:
        return _run_async(_query())
    except Exception:  # noqa: BLE001
        return []


class NemoGuardrailComponent(Node):
    display_name = "NeMo Guardrails"
    description = "Apply NeMo Guardrails to validate and filter text using a configured guardrail profile."
    icon = "Shield"
    name = "NemoGuardrails"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="The text to validate through guardrails.",
            tool_mode=True,
            required=True,
        ),
        DropdownInput(
            name="guardrail_id",
            display_name="Guardrail ID",
            info="Guardrail UUID from the Guardrails Catalogue runtime configuration.",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
            required=False,
        ),
        BoolInput(
            name="enabled",
            display_name="Enabled",
            info="If disabled, this component passes the input through unchanged.",
            value=True,
        ),
        BoolInput(
            name="fail_open",
            display_name="Fail Open",
            info="If guardrail execution fails, pass input through unchanged instead of blocking.",
            value=True,
            advanced=True,
        ),
        MultilineInput(
            name="blocked_message",
            display_name="Blocked Message",
            info="Returned when guardrails block content or fail in fail-closed mode.",
            value="Your request was blocked by configured safety guardrails.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", type_=Message, method="apply_guardrails"),
    ]

    @staticmethod
    def _extract_guardrail_uuid(raw_value: str | None) -> str:
        if not isinstance(raw_value, str):
            return ""
        value = raw_value.strip()
        if "|" in value:
            value = value.split("|")[-1].strip()
        return value

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"guardrail_id", None}:
            options = _fetch_active_guardrail_options()
            build_config["guardrail_id"]["options"] = options
            current_value = build_config["guardrail_id"].get("value", "")
            if options and current_value not in options:
                build_config["guardrail_id"]["value"] = options[0]
        return build_config

    async def apply_guardrails(self) -> Message:
        """Apply NeMo guardrails and return filtered text."""
        input_text = self.input_text if isinstance(self.input_text, str) else str(self.input_text or "")
        guardrail_id = self._extract_guardrail_uuid(self.guardrail_id)

        if not self.enabled:
            self.status = "Guardrails disabled; input passed through."
            return Message(text=input_text)

        if not guardrail_id:
            self.status = "No guardrail ID provided; input passed through."
            return Message(text=input_text)

        try:
            result = await apply_nemo_guardrail_text(
                input_text=input_text,
                guardrail_id=guardrail_id,
            )
        except Exception as exc:  # noqa: BLE001
            if self.fail_open:
                self.status = f"Guardrail execution failed in fail-open mode: {exc}"
                return Message(text=input_text)

            self.status = f"Guardrail execution failed in fail-closed mode: {exc}"
            return Message(text=self.blocked_message)

        if result.action == "blocked":
            self.status = f"Guardrail action=blocked (guardrail_id={result.guardrail_id})"
            return Message(text=self.blocked_message)

        self.status = f"Guardrail action={result.action} (guardrail_id={result.guardrail_id})"
        return Message(text=result.output_text)
