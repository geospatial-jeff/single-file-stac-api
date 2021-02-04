"""single_file_stac_api.server"""
import uvicorn
from pydantic import BaseSettings
from stac_api.api.app import StacApi, inject_settings
from stac_api.api.extensions import TransactionExtension

from single_file_stac_api.backend import SingleFileClient


def start_application(filename: str):
    """start the application."""

    class ApiSettings(BaseSettings):
        """api settings."""

        debug: bool = True
        host: str = "localhost"
        port: int = 8005

    settings = ApiSettings()
    inject_settings(settings)
    client = SingleFileClient.from_file(filename)
    api = StacApi(
        settings=settings,
        client=client,
        extensions=[TransactionExtension(client=client)],
    )
    uvicorn.run(app=api.app, host=settings.host, port=settings.port, log_level="info")
