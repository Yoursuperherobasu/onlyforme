from langchain_core.vectorstores import VectorStoreRetriever

from agentcore.custom.custom_component.custom_component import ExecutableNode
from agentcore.field_typing import VectorStore
from agentcore.inputs.inputs import HandleInput


class VectorStoreRetrieverComponent(ExecutableNode):
    display_name = "VectorStore Retriever"
    description = "A vector store retriever"
    name = "VectorStoreRetriever"
    icon = "LangChain"

    inputs = [
        HandleInput(
            name="vectorstore",
            display_name="Vector Store",
            input_types=["VectorStore"],
            required=True,
        ),
    ]

    def build(self, vectorstore: VectorStore) -> VectorStoreRetriever:
        return vectorstore.as_retriever()
