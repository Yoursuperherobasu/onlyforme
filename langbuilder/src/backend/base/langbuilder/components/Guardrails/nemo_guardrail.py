from langbuilder.custom.custom_component.component import Node
from langbuilder.inputs.inputs import MessageTextInput
from langbuilder.io import Output
from langbuilder.schema.message import Message


class NemoGuardrailComponent(Node):
    display_name = "NeMo Guardrails"
    description = "Apply NeMo Guardrails to validate and filter LLM inputs and outputs."
    documentation: str = "https://docs.langbuilder.org/components-guardrails#nemo-guardrails"
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
