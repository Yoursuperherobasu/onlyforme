from agentcore.custom.custom_component.custom_component import ExecutableNode
from agentcore.field_typing import Embeddings
from agentcore.schema.data import Data


class EmbedComponent(ExecutableNode):
    display_name = "Embed Texts"
    name = "Embed"

    def build_config(self):
        return {"texts": {"display_name": "Texts"}, "embbedings": {"display_name": "Embeddings"}}

    def build(self, texts: list[str], embbedings: Embeddings) -> Data:
        vectors = Data(vector=embbedings.embed_documents(texts))
        self.status = vectors
        return vectors
