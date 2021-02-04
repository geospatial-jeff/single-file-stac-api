"""single_file_stac_api.cli"""
import click

from single_file_stac_api.server import start_application


@click.command()
@click.argument("filepath", type=str)
def api(filepath: str):
    """start the api."""
    start_application(filepath)
