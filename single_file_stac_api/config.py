"""Config."""

from typing import Optional, Set

from pydantic import BaseSettings, Field


class ApiSettings(BaseSettings):
    """api settings."""

    debug: bool = True
    host: str = "localhost"
    port: int = 8005

    default_includes: Optional[Set[str]] = None

    # Fields which are defined by STAC but not included in the database model
    forbidden_fields: Set[str] = {"type"}

    # Fields which are item properties but indexed as distinct fields in the database model
    indexed_fields: Set[str] = Field(default_factory=set)

    class Config:
        """model config (https://pydantic-docs.helpmanual.io/usage/model_config/)."""

        env_file = ".env"
