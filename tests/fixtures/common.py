from datetime import datetime

import pytest
from freezegun import freeze_time
from python_settings import settings


@pytest.fixture(scope="function")
def mock_now():
    """Rewrite `now` for tests."""
    with freeze_time(datetime.fromtimestamp(1558923000)) as frozen_time:
        yield frozen_time


@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    """Replace settings variables for tests."""
    settings.ENVIRONMENT = "TESTING"
    settings.GCP_LOGGING = False
    settings.CSFU_TARGETS = '{"targets": [{"url": "https://example.com", "phrase_to_find": "PHRASE"}]}'
