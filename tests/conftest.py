import os

import pytest
from starlette.testclient import TestClient

from single_file_stac_api.backend import SingleFileClient
from single_file_stac_api.server import Application

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture
def app_client():
    """client fixture."""
    host = "localhost"
    port = 8005
    filepath = os.path.join(DATA_DIR, "test-data.json")

    client = SingleFileClient(filepath=filepath, host=f"http://{host}:{port}")
    app = Application(client, host=host, port=port)
    with TestClient(app.stac_api.app) as test_client:
        yield test_client
