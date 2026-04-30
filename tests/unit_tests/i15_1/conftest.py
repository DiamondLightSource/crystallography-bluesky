import pytest
from bluesky import RunEngine


@pytest.fixture
def run_engine():
    return RunEngine()
