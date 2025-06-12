from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.notion import (
    INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME,
    INCIDENT_SHIFT_ATTRIBUTE_NAME,
    Alert,
    AlertAnnotations,
    AlertLabels,
    NotionService,
)


@pytest.fixture
def notion_service(monkeypatch):
    """Fixture for NotionService instance."""
    monkeypatch.setattr("app.services.notion.Client", MagicMock())
    return NotionService(token="token", incidents_db_id="dbid", shifts_db_id="", shifts_enabled=False)


@pytest.fixture
def notion_service_with_shifts(monkeypatch):
    """Fixture for NotionService instance with shifts enabled."""
    monkeypatch.setattr("app.services.notion.Client", MagicMock())
    return NotionService(
        token="token",
        incidents_db_id="incidents_db_id",
        shifts_db_id="shifts_db_id",
        shifts_enabled=True,
    )


def test_find_incident_page_by_fingerprint_found(notion_service):
    """Test finding an incident page by fingerprint."""
    notion_service.client.databases.query.return_value = {"results": [{"id": "page-1"}]}
    page_id = notion_service.find_incident_page_by_fingerprint("abc123")
    notion_service.client.databases.query.assert_called_once_with(
        database_id=notion_service.incidents_db_id,
        filter={"property": "AMFingerprint", "rich_text": {"equals": "abc123"}},
    )
    assert page_id == "page-1"


def test_find_incident_page_by_fingerprint_not_found(notion_service):
    """Test finding an incident page by fingerprint when not found."""
    notion_service.client.databases.query.return_value = {"results": []}
    page_id = notion_service.find_incident_page_by_fingerprint("notfound")
    assert page_id is None


def test_update_incident_status(alert_payload, notion_service):
    """Test updating the status of an incident."""
    alert = Alert.model_validate(alert_payload["alerts"][0])
    notion_service.update_incident_status("page-1", alert)
    notion_service.client.pages.update.assert_called_once_with(
        page_id="page-1",
        properties={
            "AMStatus": {"select": {"name": "Resolved"}},
            "Incident Timeframe": {"date": {"start": "2025-06-10T23:15:15.277Z", "end": "2025-06-11T19:44:45.277Z"}},
        },
    )


def test_create_incident_page_from_alert_no_shift(notion_service):
    """Test creating an incident page from an alert when no shift is found."""
    alert = Alert(
        status="firing",
        labels=None,
        annotations=None,
        startsAt="2025-06-08T07:00:00Z",
        endsAt="0001-01-01T00:00:00Z",
        generatorURL=None,
        fingerprint="abc123",
    )
    # Patch _get_shift to return (None, [])
    with patch.object(notion_service, "_get_shift", return_value=(None, [])):
        notion_service.create_incident_page_from_alert(alert)
    called_props = notion_service.client.pages.create.call_args[1]["properties"]
    assert INCIDENT_SHIFT_ATTRIBUTE_NAME not in called_props
    assert INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME not in called_props
    assert called_props["AMFingerprint"]["rich_text"][0]["text"]["content"] == "abc123"


def test_create_incident_page_from_alert_with_shift(notion_service_with_shifts):
    """Test creating an incident page from an alert when a shift is found."""
    alert = Alert(
        status="firing",
        labels=None,
        annotations=None,
        startsAt="2025-06-08T07:00:00Z",
        endsAt="0001-01-01T00:00:00Z",
        generatorURL=None,
        fingerprint="abc123",
    )
    shift_page_id = "shift123"
    shift_responsible = [{"id": "person1"}]
    with patch.object(notion_service_with_shifts, "_get_shift", return_value=(shift_page_id, shift_responsible)):
        notion_service_with_shifts.create_incident_page_from_alert(alert)
    called_props = notion_service_with_shifts.client.pages.create.call_args[1]["properties"]
    assert INCIDENT_SHIFT_ATTRIBUTE_NAME in called_props
    assert called_props[INCIDENT_SHIFT_ATTRIBUTE_NAME]["relation"] == [{"id": shift_page_id}]
    assert called_props[INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME]["people"] == shift_responsible


def test_create_incident_page_shifts_disabled(notion_service):
    """Test creating an incident page when shifts are disabled."""
    alert = Alert(
        status="firing",
        labels=None,
        annotations=None,
        startsAt="2025-06-08T07:00:00Z",
        endsAt="0001-01-01T00:00:00Z",
        generatorURL=None,
        fingerprint="abc123",
    )
    with patch.object(notion_service, "_get_shift", return_value=(None, [])):
        notion_service.create_incident_page_from_alert(alert)
    called_props = notion_service.client.pages.create.call_args[1]["properties"]
    assert INCIDENT_SHIFT_ATTRIBUTE_NAME not in called_props
    assert INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME not in called_props


def test_handle_alert_creates_and_updates(notion_service_with_shifts):
    """Test handling an alert that creates and updates incident pages."""
    with (
        patch.object(
            notion_service_with_shifts,
            "find_incident_page_by_fingerprint",
            side_effect=[None, "page-2"],
        ) as mock_find,
        patch.object(notion_service_with_shifts, "update_incident_status") as mock_update,
        patch.object(notion_service_with_shifts, "create_incident_page_from_alert") as mock_create,
    ):
        alert_payload = {
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
                {
                    "status": "resolved",
                    "labels": {"alertname": "b", "instance": "j", "severity": "w"},
                    "annotations": {"description": "d2", "summary": "s2"},
                    "startsAt": "2025-06-08T08:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "",
                    "fingerprint": "def456",
                },
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
            "version": "4",
            "groupKey": "",
            "truncatedAlerts": 0,
        }
        notion_service_with_shifts.handle_alert(alert_payload)
        # Проверяем, что методы были вызваны с ожидаемыми аргументами
        expected_alert_1 = Alert(
            status="firing",
            labels=AlertLabels(alertname="a", instance="i", severity="s"),
            annotations=AlertAnnotations(description="d", summary="s"),
            startsAt="2025-06-08T07:00:00Z",
            endsAt="0001-01-01T00:00:00Z",
            generatorURL="",
            fingerprint="abc123",
        )
        expected_alert_2 = Alert(
            status="resolved",
            labels=AlertLabels(alertname="b", instance="j", severity="w"),
            annotations=AlertAnnotations(description="d2", summary="s2"),
            startsAt="2025-06-08T08:00:00Z",
            endsAt="0001-01-01T00:00:00Z",
            generatorURL="",
            fingerprint="def456",
        )
        mock_find.assert_any_call("abc123")
        mock_find.assert_any_call("def456")
        mock_create.assert_called_once()
        called_alert = mock_create.call_args[0][0]
        assert called_alert.fingerprint == expected_alert_1.fingerprint
        assert called_alert.status == expected_alert_1.status
        mock_update.assert_called_once_with("page-2", expected_alert_2)


def test_get_shift_disabled(notion_service):
    """Test _get_shift returns (None, []) when shifts are disabled."""
    shift_id, responsible = notion_service._get_shift()
    assert shift_id is None
    assert responsible == []


def test_get_shift_with_type_enabled(notion_service_with_shifts):
    """Test _get_shift returns correct shift and responsible when shift type filter is enabled."""
    notion_service_with_shifts.client.databases.query.return_value = {
        "results": [
            {
                "id": "shift-1",
                "properties": {
                    "On-Duty": {
                        "people": [{"id": "person-1"}],
                    },
                },
            },
        ],
    }
    notion_service_with_shifts.shifts_enabled = True
    shift_id, responsible = notion_service_with_shifts._get_shift()
    assert shift_id == "shift-1"
    assert responsible == [{"id": "person-1"}]
    notion_service_with_shifts.client.databases.query.assert_called_once()
    args, kwargs = notion_service_with_shifts.client.databases.query.call_args
    assert kwargs["database_id"] == notion_service_with_shifts.shifts_db_id
    assert "Shift Type" in str(kwargs["filter"])


def test_get_shift_without_type(notion_service_with_shifts, monkeypatch):
    """Test _get_shift returns correct shift and responsible when shift type filter is enabled."""
    monkeypatch.setattr("app.services.notion.FIND_FOR_CURRENT_SHIFT_TYPE_ENABLED", False)
    notion_service_with_shifts.client.databases.query.return_value = {
        "results": [
            {
                "id": "shift-1",
                "properties": {
                    "On-Duty": {
                        "people": [{"id": "person-1"}],
                    },
                },
            },
        ],
    }
    notion_service_with_shifts.shifts_enabled = True
    shift_id, responsible = notion_service_with_shifts._get_shift()
    assert shift_id == "shift-1"
    assert responsible == [{"id": "person-1"}]
    notion_service_with_shifts.client.databases.query.assert_called_once()
    args, kwargs = notion_service_with_shifts.client.databases.query.call_args
    assert kwargs["database_id"] == notion_service_with_shifts.shifts_db_id
    assert "Shift Type" not in str(kwargs["filter"])


def test_get_shift_with_type_enabled_no_results(notion_service_with_shifts):
    """Test _get_shift returns (None, []) when no shift found."""
    notion_service_with_shifts.client.databases.query.return_value = {"results": []}
    notion_service_with_shifts.shifts_enabled = True
    shift_id, responsible = notion_service_with_shifts._get_shift()
    assert shift_id is None
    assert responsible == []


def test_get_shift_http_error(notion_service_with_shifts):
    """Test _get_shift returns (None, []) on httpx.HTTPError."""
    notion_service_with_shifts.client.databases.query.side_effect = httpx.HTTPError("http error")
    notion_service_with_shifts.shifts_enabled = True
    shift_id, responsible = notion_service_with_shifts._get_shift()
    assert shift_id is None
    assert responsible == []


@patch("app.services.notion.logger")
def test_handle_alert_parse_error(mock_logger, notion_service):
    """Test handle_alert logs and returns on parse error."""
    notion_service.handle_alert({"invalid": "data"})
    mock_logger.exception.assert_called_once()
    assert "Failed to parse Alertmanager event" in mock_logger.exception.call_args[0][0]
