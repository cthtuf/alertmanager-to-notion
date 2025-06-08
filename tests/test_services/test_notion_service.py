from unittest.mock import MagicMock, patch

import pytest

from app.services.notion import AlertmanagerEvent, NotionService


@pytest.fixture
def notion_service():
    """Fixture for NotionService instance."""
    return NotionService(token="token", db_id="dbid")


@pytest.fixture
def alert_payload():
    """Fixture for a sample Alertmanager event payload."""
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


@patch("requests.request")
def test_notion_service_request_sends_correct_data(mock_request, notion_service):
    """Test that _request sends correct data to Notion API."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_request.return_value = mock_resp
    url = "https://api.notion.com/v1/pages"
    data = {"foo": "bar"}
    notion_service._request("POST", url, json=data)
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert args[1] == url
    assert kwargs["json"] == data
    assert kwargs["timeout"] == 10
    headers = kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {notion_service.token}"
    assert headers["Notion-Version"] == notion_service.notion_version
    assert headers["Content-Type"] == "application/json"


@patch("app.services.notion.logger")
@patch("requests.request")
def test_notion_service_request_http_error(mock_request, mock_logger, notion_service):
    """Test that _request raises and logs on HTTP error."""
    from requests import HTTPError

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = HTTPError("fail")
    mock_resp.text = "error text"
    mock_request.return_value = mock_resp
    with pytest.raises(HTTPError):
        notion_service._request("POST", "http://url", json={})
    mock_logger.error.assert_called_once()
    assert "Notion API error" in mock_logger.error.call_args[0][0]


@patch.object(NotionService, "_request")
def test_notion_service_find_page_by_fingerprint_found(mock_request, notion_service):
    """Test that find_page_by_fingerprint returns page ID when found."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": "page-1"}]}
    mock_request.return_value = mock_resp
    page_id = notion_service.find_page_by_fingerprint("abc123")
    mock_request.assert_called_once_with(
        "POST",
        f"https://api.notion.com/v1/databases/{notion_service.db_id}/query",
        json={
            "filter": {
                "property": "AMFingerprint",
                "rich_text": {"equals": "abc123"},
            },
        },
    )
    assert page_id == "page-1"


@patch.object(NotionService, "_request")
def test_notion_service_find_page_by_fingerprint_not_found(mock_request, notion_service):
    """Test that find_page_by_fingerprint returns None when not found."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_request.return_value = mock_resp
    page_id = notion_service.find_page_by_fingerprint("notfound")
    mock_request.assert_called_once_with(
        "POST",
        f"https://api.notion.com/v1/databases/{notion_service.db_id}/query",
        json={
            "filter": {
                "property": "AMFingerprint",
                "rich_text": {"equals": "notfound"},
            },
        },
    )
    assert page_id is None


@patch.object(NotionService, "_request")
def test_notion_service_update_page_status(mock_request, notion_service):
    """Test that update_page_status sends correct data to Notion API."""
    mock_request.return_value = MagicMock()
    notion_service.update_page_status("page-1", "Firing")
    mock_request.assert_called_once_with(
        "PATCH",
        "https://api.notion.com/v1/pages/page-1",
        json={
            "properties": {
                "AMStatus": {"select": {"name": "Firing"}},
            },
        },
    )


@patch.object(NotionService, "_request")
def test_notion_service_create_page_from_alert(mock_request, notion_service):
    """Test that create_page_from_alert sends correct data to Notion API."""
    mock_request.return_value = MagicMock()
    alert = AlertmanagerEvent.model_validate(
        {
            "receiver": "r",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "a", "instance": "i", "severity": "s"},
                    "annotations": {"description": "d", "summary": "s"},
                    "startsAt": "2025-06-08T07:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "",
                    "fingerprint": "abc123",
                },
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
            "version": "4",
            "groupKey": "",
            "truncatedAlerts": 0,
        },
    ).alerts[0]
    notion_service.create_page_from_alert(alert)
    mock_request.assert_called_once_with(
        "POST",
        notion_service.api_url,
        json={
            "parent": {"database_id": notion_service.db_id},
            "properties": {
                "AMFingerprint": {"rich_text": [{"text": {"content": "abc123"}}]},
                "AMStatus": {"select": {"name": "Firing"}},
            },
        },
    )


@patch.object(NotionService, "find_page_by_fingerprint")
@patch.object(NotionService, "update_page_status")
@patch.object(NotionService, "create_page_from_alert")
def test_notion_service_handle_alert_logic(mock_create, mock_update, mock_find, notion_service, alert_payload):
    """Test the handle_alert logic for both firing and resolved alerts."""
    # Simulate: first alert not found, second alert found
    alert_payload["alerts"].append(
        {
            "status": "resolved",
            "labels": {"alertname": "TestAlert2", "instance": "host:456", "severity": "warning"},
            "annotations": {"description": "desc2", "summary": "sum2"},
            "startsAt": "2025-06-08T08:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "",
            "fingerprint": "def456",
        },
    )
    mock_find.side_effect = [None, "page-2"]
    notion_service.handle_alert(alert_payload)
    mock_create.assert_called_once_with(mock_create.call_args[0][0])
    mock_update.assert_called_once_with("page-2", "Resolved")


@patch("app.services.notion.logger")
def test_notion_service_handle_alert_invalid_event(mock_logger, notion_service):
    """Test that handle_alert logs an exception for invalid event data."""
    notion_service.handle_alert({"invalid": "data"})
    mock_logger.exception.assert_called()
