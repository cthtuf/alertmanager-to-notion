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
    handler = NotionHandler(alert_payload, Context())
    handler()
    mock_handle_alert.assert_called_once_with(alert_payload)
