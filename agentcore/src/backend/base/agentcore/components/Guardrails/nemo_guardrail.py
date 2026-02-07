from agentcore.custom.custom_node.node import Node
from agentcore.inputs.inputs import MessageTextInput
from agentcore.io import Output
from agentcore.schema.message import Message


class NemoGuardrailComponent(Node):
    display_name = "NeMo Guardrails"
    description = "Apply NeMo Guardrails to validate and filter LLM inputs and outputs."
    icon = "Shield"
    name = "NemoGuardrails"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="The text to validate through guardrails.",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", type_=Message, method="apply_guardrails"),
    ]

    def apply_guardrails(self) -> Message:
        """Apply guardrails to the input text and return the result."""
        # Placeholder implementation - can be extended with actual NeMo Guardrails logic
        result = self.input_text
        self.status = "Guardrails applied successfully"
        return Message(text=result)
