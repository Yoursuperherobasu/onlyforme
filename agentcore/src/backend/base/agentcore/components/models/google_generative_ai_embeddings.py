from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings as LCGoogleGenerativeAIEmbeddings

from agentcore.custom.custom_node.node import Node
from agentcore.io import IntInput, MessageTextInput, Output, SecretStrInput

MAX_DIMENSION = 768
MIN_DIMENSION = 1


class GoogleGenerativeAIEmbeddings(Node):
    display_name = "Google Generative AI Embeddings"
    description = (
        "Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, "
        "found in the langchain-google-genai package."
    )
    icon = "GoogleGenerativeAI"
    name = "Google Generative AI Embeddings"

    inputs = [
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        MessageTextInput(name="model_name", display_name="Model Name", value="models/text-embedding-004"),
        IntInput(
            name="output_dimensionality",
            display_name="Output Dimensionality",
            value=768,
            advanced=True,
            info="Optional reduced dimension for the output embedding. Max 768.",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.api_key:
            msg = "API Key is required"
            raise ValueError(msg)

        dimensionality = getattr(self, "output_dimensionality", None)
        if dimensionality is not None:
            if dimensionality < MIN_DIMENSION:
                msg = "Output dimensionality must be at least 1"
                raise ValueError(msg)
            if dimensionality > MAX_DIMENSION:
                msg = "Output dimensionality cannot exceed 768. Google's embedding models only support dimensions up to 768."
                raise ValueError(msg)

        return LCGoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=self.api_key,
            output_dimensionality=dimensionality,
        )
