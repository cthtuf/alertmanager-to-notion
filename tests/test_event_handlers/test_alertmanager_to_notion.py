import base64
import json
from unittest.mock import patch

import pytest
from google.cloud.functions_v1.context import Context

from app.event_handlers.notion import NotionHandler


@pytest.fixture
def alert_payload():
    """Fixture for alert payload."""
    return {
        "receiver": "webhook-site-receiver",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "TestAlert", "instance": "host:123", "severity": "critical"},
                "annotations": {"description": "desc", "summary": "sum"},
                "startsAt": "2025-06-08T07:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            },
        ],
        "groupLabels": {},
        "commonLabels": {},
        "commonAnnotations": {},
        "externalURL": "http://localhost:9093",
        "version": "4",
        "groupKey": '{}:{alertname="TestAlert"}',
        "truncatedAlerts": 0,
    }


@patch("app.services.notion.NotionService.handle_alert")
def test_notion_handler_calls_service(mock_handle_alert, alert_payload):
    """Test that NotionHandler calls NotionService with the correct payload."""
    json_payload = json.dumps(alert_payload).encode("utf-8")
    b64_payload = base64.b64encode(json_payload).decode("utf-8")
    event = {
        "data": b64_payload,
        "message_id": "15146915485216343",
        "publish_time": "2025-06-11T19:01:45.439Z",
    }
    handler = NotionHandler(event, Context())
    handler()
    mock_handle_alert.assert_called_once_with(alert_payload)
