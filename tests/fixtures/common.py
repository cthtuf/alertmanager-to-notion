import pytest
from python_settings import settings


@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    """Replace settings variables for tests."""
    settings.ENVIRONMENT = "TESTING"
    settings.GCP_LOGGING = False
