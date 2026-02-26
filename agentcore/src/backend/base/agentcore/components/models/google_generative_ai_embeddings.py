import os

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from agentcore.custom.custom_node.node import Node
from agentcore.io import IntInput, MessageTextInput, Output


MAX_DIMENSION = 3072
MIN_DIMENSION = 1


class GoogleGenerativeAIEmbeddingsNode(Node):
    display_name = "Google Generative AI Embeddings"
    description = (
        "Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, "
        "found in the langchain-google-genai package."
    )
    icon = "GoogleGenerativeAI"
    name = "Google Generative AI Embeddings"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            value="models/gemini-embedding-001",
        ),
        IntInput(
            name="output_dimensionality",
            display_name="Output Dimensionality",
            value=768,
            advanced=True,
            info="Optional reduced dimension for the output embedding.",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        dimensionality = getattr(self, "output_dimensionality", None)
        if dimensionality is not None:
            if dimensionality < MIN_DIMENSION:
                raise ValueError("Output dimensionality must be at least 1")
            if dimensionality > MAX_DIMENSION:
                raise ValueError(f"Output dimensionality cannot exceed {MAX_DIMENSION}.")

        return GoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=os.environ["GOOGLE_API_KEY"],
            output_dimensionality=dimensionality,
        )
