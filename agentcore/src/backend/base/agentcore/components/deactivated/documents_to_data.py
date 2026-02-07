from langchain_core.documents import Document

from agentcore.custom.custom_node.custom_node import ExecutableNode
from agentcore.schema.data import Data


class DocumentsToDataComponent(ExecutableNode):
    display_name = "Documents ⇢ Data"
    description = "Convert LangChain Documents into Data."
    icon = "LangChain"
    name = "DocumentsToData"

    field_config = {
        "documents": {"display_name": "Documents"},
    }

    def build(self, documents: list[Document]) -> list[Data]:
        if isinstance(documents, Document):
            documents = [documents]
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
