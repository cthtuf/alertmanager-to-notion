import json

import pytest
from app.models import WebsiteContent
from python_settings import settings


@pytest.fixture
def website_content_obj():
    """Website content mocked object."""
    target = json.loads(settings.CSFU_TARGETS)["targets"][0]
    obj = WebsiteContent(
        url=target["url"],
        content_snapshot="last content",
    )
    obj.save()
    return obj
