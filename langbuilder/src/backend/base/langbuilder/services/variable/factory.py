from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langbuilder.services.factory import ServiceFactory
from langbuilder.services.variable.base import VariableService
from langbuilder.services.variable.service import DatabaseVariableService

if TYPE_CHECKING:
    from langbuilder.services.settings.service import SettingsService


class VariableServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(VariableService)

    @override
    def create(self, settings_service: SettingsService):
        return DatabaseVariableService(settings_service)
