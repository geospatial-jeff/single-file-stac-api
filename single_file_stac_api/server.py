"""single_file_stac_api.server"""
from typing import Optional

import attr
import uvicorn
from stac_api.api.app import StacApi, inject_settings
from stac_api.api.extensions import (
    ContextExtension,
    FieldsExtension,
    TransactionExtension,
)

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.config import ApiSettings


@attr.s
class Application:
    """api application."""

    client: SingleFileClient = attr.ib()
    host: Optional[str] = attr.ib(default="localhost")
    port: Optional[int] = attr.ib(default=8005)

    settings: ApiSettings = attr.ib(init=False)
    stac_api: StacApi = attr.ib(init=False)

    def __attrs_post_init__(self):
        """post init hook."""
        self.settings = ApiSettings(host=self.host, port=self.port)
        inject_settings(self.settings)

        self.stac_api = StacApi(
            settings=self.settings,
            client=self.client,
            extensions=[
                TransactionExtension(client=self.client),
                ContextExtension(),
                FieldsExtension(),
            ],
        )

    def run(self):
        """serve the application."""
        uvicorn.run(
            app=self.stac_api.app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
        )
