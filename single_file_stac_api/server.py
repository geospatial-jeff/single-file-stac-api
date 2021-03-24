"""single_file_stac_api.server"""
import pathlib
from typing import Optional

import attr
import uvicorn
from stac_api.api.app import StacApi, inject_settings
from stac_api.api.extensions import (
    ContextExtension,
    FieldsExtension,
    TransactionExtension,
)
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.config import ApiSettings

template_dir = str(pathlib.Path(__file__).parent.joinpath("templates"))
templates = Jinja2Templates(directory=template_dir)


@attr.s
class Application:
    """api application."""

    client: SingleFileClient = attr.ib()
    host: Optional[str] = attr.ib(default="localhost")
    port: Optional[int] = attr.ib(default=8005)
    style: Optional[str] = attr.ib(default="dark")
    token: Optional[str] = attr.ib(default="")

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
                FieldsExtension(
                    default_includes={
                        "id",
                        "type",
                        "geometry",
                        "bbox",
                        "links",
                        "assets",
                        "collection",
                        "properties.datetime",
                    }
                ),
            ],
        )

        @self.stac_api.app.get(
            "/index.html",
            response_class=HTMLResponse,
        )
        async def viewer(request: Request):
            """Handle /index.html."""
            return templates.TemplateResponse(
                name="index.html",
                context={
                    "request": request,
                    "collection_endpoint": f"http://{self.host}:{self.port}/collections",
                    "search_endpoint": f"http://{self.host}:{self.port}/search",
                    "mapbox_access_token": self.token,
                    "mapbox_style": self.style,
                },
                media_type="text/html",
            )

    def run(self):
        """serve the application."""
        uvicorn.run(
            app=self.stac_api.app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
        )
