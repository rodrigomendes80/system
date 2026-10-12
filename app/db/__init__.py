from app.config import Settings
from app.db.base import Database


def create_database(settings: Settings) -> Database:
    if settings.db_backend == "databricks":
        from app.db.databricks import DatabricksDatabase

        return DatabricksDatabase(
            server_hostname=settings.databricks_server_hostname,
            http_path=settings.databricks_http_path,
            warehouse_id=settings.databricks_warehouse_id,
            catalog=settings.databricks_catalog,
            schema=settings.databricks_schema,
            access_token=settings.databricks_token,
        )
    from app.db.sqlite import SQLiteDatabase

    return SQLiteDatabase(settings.sqlite_path)
