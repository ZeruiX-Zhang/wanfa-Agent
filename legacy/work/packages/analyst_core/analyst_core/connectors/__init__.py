from analyst_core.connectors.base import StructuredDataConnector
from analyst_core.connectors.sqlite_demo import SQLiteDemoConnector
from analyst_core.connectors.warehouse_readonly import WarehouseReadonlyConnector
from analyst_core.core.config import Settings


def get_connector(settings: Settings) -> StructuredDataConnector:
    if settings.structured_data_connector == "warehouse_readonly":
        return WarehouseReadonlyConnector(settings)
    return SQLiteDemoConnector(settings)


__all__ = [
    "StructuredDataConnector",
    "SQLiteDemoConnector",
    "WarehouseReadonlyConnector",
    "get_connector",
]
