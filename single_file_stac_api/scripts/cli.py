"""single_file_stac_api.cli"""
import click

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.server import Application


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
    client = SingleFileClient(filepath=filepath, host=f"http://{host}:{port}")
    app = Application(client, host=host, port=port)
    app.run()
