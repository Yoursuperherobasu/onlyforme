from fastapi_pagination import Page

from agentcore.helpers.base_model import BaseModel
from agentcore.services.database.models.flow.model import Flow
from agentcore.services.database.models.folder.model import FolderRead


class FolderWithPaginatedFlows(BaseModel):
    folder: FolderRead
    flows: Page[Flow]
