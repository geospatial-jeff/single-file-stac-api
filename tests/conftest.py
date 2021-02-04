import os

import pytest
from starlette.testclient import TestClient

from single_file_stac_api.server import Application

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture
def app_client():
    app = Application.from_file(os.path.join(DATA_DIR, "test-data.json"))
    with TestClient(app.stac_api.app) as test_client:
        yield test_client
