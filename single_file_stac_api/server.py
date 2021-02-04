"""single_file_stac_api.server"""
from dataclasses import dataclass

import uvicorn
from pydantic import BaseSettings
from stac_api.api.app import StacApi, inject_settings
from stac_api.api.extensions import TransactionExtension

from single_file_stac_api.backend import SingleFileClient


class ApiSettings(BaseSettings):
    """api settings."""

    debug: bool = True
    host: str = "localhost"
    port: int = 8005


@dataclass
class Application:
    """api application."""

    client: SingleFileClient
    settings: ApiSettings

    @classmethod
    def from_file(cls, filename: str):
        """create from file."""
        settings = ApiSettings()
        inject_settings(settings)
        return cls(
            client=SingleFileClient.from_file(filename),
            settings=settings,
        )

    def __post_init__(self):
        """post init hook."""
        self.stac_api = StacApi(
            settings=self.settings,
            client=self.client,
            extensions=[TransactionExtension(client=self.client)],
        )

    def run(self):
        """serve the application."""
        uvicorn.run(
            app=self.stac_api.app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
        )


def start_application(filename: str):
    """start the application."""
    app = Application.from_file(filename)
    app.run()
