"""single_file_stac_api.cli"""
import os

import click

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.server import Application


class MbxTokenType(click.ParamType):
    """Mapbox token type."""

    name = "token"

    def convert(self, value, param, ctx):
        """Validate token."""
        try:
            if not value:
                return ""

            assert value.startswith("pk")
            return value

        except (AttributeError, AssertionError):
            raise click.ClickException(
                "Mapbox access token must be public (pk). "
                "Please sign up at https://www.mapbox.com/signup/ to get a public token. "
                "If you already have an account, you can retreive your "
                "token at https://www.mapbox.com/account/."
            )


@click.command()
@click.argument("filepath", type=str)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="Webserver host url (default: localhost)",
)
@click.option("--port", type=int, default=8005, help="Webserver port (default: 8005)")
def api(filepath, host, port):
    """start the api."""
    client = SingleFileClient(filepath=filepath)
    app = Application(client, host=host, port=port)
    app.run()


@click.command()
@click.argument("filepath", type=str)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="Webserver host url (default: localhost)",
)
@click.option("--port", type=int, default=8005, help="Webserver port (default: 8005)")
@click.option(
    "--style",
    type=click.Choice(["dark", "satellite", "basic"]),
    default="dark",
    help="Mapbox basemap",
)
@click.option(
    "--mapbox-token",
    type=MbxTokenType(),
    metavar="TOKEN",
    default=lambda: os.environ.get("MAPBOX_ACCESS_TOKEN", ""),
    help="Pass Mapbox token",
)
def viz(filepath, host, port, style, mapbox_token):
    """start the api."""
    client = SingleFileClient(filepath=filepath)
    app = Application(client, host=host, port=port, style=style, token=mapbox_token)

    click.launch(f"http://{host}:{port}/index.html")
    app.run()
