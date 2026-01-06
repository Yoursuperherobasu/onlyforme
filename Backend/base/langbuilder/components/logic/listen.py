from langbuilder.custom import Component
from langbuilder.io import Output, StrInput
from langbuilder.schema.data import Data


class ListenComponent(Component):
    display_name = "Listen"
    description = "A component to listen for a notification."
    name = "Listen"
    beta: bool = True
    icon = "Radio"
    inputs = [
        StrInput(
            name="context_key",
            display_name="Context Key",
            info="The key of the context to listen for.",
            input_types=["Message"],
            required=True,
        )
    ]

    outputs = [Output(name="data", display_name="Data", method="listen_for_data", cache=False)]

    def listen_for_data(self) -> Data:
        """Retrieves a Data object from the component context using the provided context key.

        If the specified context key does not exist in the context, returns an empty Data object.
        """
        # Convert context_key to string if it's a Message object
        from langbuilder.schema.message import Message
        
        context_key = self.context_key
        if isinstance(context_key, Message):
            context_key = context_key.text
        
        return self.ctx.get(context_key, Data(text=""))
