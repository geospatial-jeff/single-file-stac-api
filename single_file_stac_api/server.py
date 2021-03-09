"""single_file_stac_api.server"""
from dataclasses import dataclass

import uvicorn
from stac_api.api.app import StacApi, inject_settings
from stac_api.api.extensions import (
    ContextExtension,
    FieldsExtension,
    TransactionExtension,
)

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.config import settings


@dataclass
class Application:
    """api application."""

    client: SingleFileClient

    def __post_init__(self):
        """post init hook."""
        self.stac_api = StacApi(
            settings=settings,
            client=self.client,
            extensions=[
                TransactionExtension(client=self.client),
                ContextExtension(),
                FieldsExtension(),
            ],
        )

    @classmethod
    def from_file(cls, filename: str):
        """create from file."""
        inject_settings(settings)
        return cls(client=SingleFileClient.from_file(filename))

    def run(self):
        """serve the application."""
        uvicorn.run(
            app=self.stac_api.app,
            host=settings.host,
            port=settings.port,
            log_level="info",
        )


def start_application(filename: str):
    """start the application."""
    app = Application.from_file(filename)
    app.run()
