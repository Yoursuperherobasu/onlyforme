from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from agentcore.services.factory import ServiceFactory
from agentcore.services.variable.base import VariableService
from agentcore.services.variable.service import DatabaseVariableService

if TYPE_CHECKING:
    from agentcore.services.settings.service import SettingsService


class VariableServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(VariableService)

    @override
    def create(self, settings_service: SettingsService):
        return DatabaseVariableService(settings_service)
