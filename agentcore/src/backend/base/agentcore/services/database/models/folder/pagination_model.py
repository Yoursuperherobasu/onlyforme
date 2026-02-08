from fastapi_pagination import Page
from pydantic import Field

from agentcore.helpers.base_model import BaseModel
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.folder.model import FolderRead


class FolderWithPaginatedAgents(BaseModel):
    model_config = {"populate_by_name": True}

    folder: FolderRead
    agents: Page[Agent] = Field(serialization_alias="flows")
