from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_backend: Literal["databricks", "sqlite"] = "sqlite"
    sqlite_path: str = "gestao_projetos.db"

    databricks_server_hostname: str = ""
    databricks_http_path: str = ""
    databricks_token: str = ""
    databricks_catalog: str = "main"
    databricks_schema: str = "gestao_projetos"


@lru_cache
def get_settings() -> Settings:
    return Settings()
