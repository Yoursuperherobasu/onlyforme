from langbuilder.base.io.text import TextNode
from langbuilder.io import MultilineInput, Output
from langbuilder.schema.message import Message


class TextInput(TextNode):
    display_name = "Text Input"
    description = "Get user text inputs."
    icon = "type"
    name = "TextInput"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input.",
        ),
    ]
    outputs = [
        Output(display_name="Output Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Message:
        return Message(
            text=self.input_value,
        )
