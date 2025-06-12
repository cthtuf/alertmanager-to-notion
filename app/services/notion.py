import typing as t

import logging
from datetime import datetime

import httpx
import pytz
from notion_client import Client
from pydantic import BaseModel, computed_field
from python_settings import settings

logger = logging.getLogger("notion-service")

# --- Pydantic Schemas for Prometheus Alertmanager Webhook ---
# https://prometheus.io/docs/alerting/latest/notifications/#data-structures


class AlertLabels(BaseModel):
    """Labels for an alert, used to identify and categorize the alert."""

    alertname: str | None = None
    instance: str | None = None
    severity: str | None = None


class AlertAnnotations(BaseModel):
    """Annotations for an alert, providing additional information."""

    description: str | None = None
    summary: str | None = None


class Alert(BaseModel):
    """Represents an alert from Alertmanager."""

    status: str
    labels: AlertLabels | None = None
    annotations: AlertAnnotations | None = None
    startsAt: str
    endsAt: str
    generatorURL: str | None = None
    fingerprint: str

    @computed_field  # type: ignore
    @property
    def notion_status(self) -> str:
        """Convert Alert status to Notion status."""
        return self.status.capitalize()


class AlertmanagerEvent(BaseModel):
    """Represents an Alertmanager event containing multiple alerts."""

    receiver: str
    status: str
    alerts: list[Alert]
    groupLabels: dict[str, t.Any]
    commonLabels: dict[str, t.Any]
    commonAnnotations: dict[str, t.Any]
    externalURL: str
    version: str
    groupKey: str
    truncatedAlerts: int


# --- NotionService ---
# Set it to empty value if you have only one shift type and don't need to filter by shift type.
FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_NAME = "Shift Type"
FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_VALUE = "Daily"
SHIFT_RESPONSIBLE_ATTRIBUTE_NAME = "On-Duty"
INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME = "Responsible"
INCIDENT_SHIFT_ATTRIBUTE_NAME = "Shift"
FIND_FOR_CURRENT_SHIFT_TYPE_ENABLED = (
    FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_NAME and FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_VALUE
)


class NotionService:
    """
    Service for interacting with Notion API to manage pages in an Incident Database based on Alertmanager events.

    Supports Shifts table for auto-assigning incidents.
    """

    def __init__(
        self,
        token: str,
        incidents_db_id: str,
        shifts_db_id: str,
        shifts_enabled: bool,
        notion_version: str = "2022-06-28",
    ):
        """Initialize NotionService with required parameters."""
        self.token = token
        self.incidents_db_id = incidents_db_id
        self.shifts_db_id = shifts_db_id
        self.shifts_enabled = shifts_enabled
        self.notion_version = notion_version
        self.client = Client(auth=token)

    def find_incident_page_by_fingerprint(self, fingerprint: str) -> str | None:
        """Find a Notion page by its `AMFingerprint` value."""
        resp = self.client.databases.query(
            database_id=self.incidents_db_id,
            filter={
                "property": "AMFingerprint",
                "rich_text": {"equals": fingerprint},
            },
        )
        if incident_page := next(iter(resp.get("results", [])), None):  # type: ignore
            logger.info("Fingerprint %s found in Notion, page ID: %s", fingerprint, incident_page["id"])
            return incident_page["id"]

        logger.debug("Fingerprint %s not found in Notion, response=%s", fingerprint, resp)

        return None

    def update_incident_status(self, page_id: str, alert: Alert) -> None:
        """Update the status of an incident."""
        status = alert.notion_status
        properties = {
            "AMStatus": {"select": {"name": status}},
        }
        if status == "Resolved":
            properties["Incident Timeframe"] = {
                "date": {
                    "start": alert.startsAt,
                    "end": alert.endsAt,
                },
            }
        self.client.pages.update(
            page_id=page_id,
            properties=properties,
        )
        logger.info(f"Updated Notion page {page_id} with status {status}")

    def _get_shift(self) -> tuple[int | None, list[dict[str, t.Any]]]:
        """
        Find a responsible person for today's daily shift in Shifts DB.

        Returns a tuple of shift ID and list of responsible persons.
        """
        if not self.shifts_enabled:
            logger.debug(
                "Shifts support is not enabled or Shifts DB ID is not set: %s, %s",
                settings.AM2N_SHIFTS_SUPPORT_ENABLED,
                settings.AM2N_SHIFTS_DB_ID,
            )
            return None, []

        today = datetime.now(tz=pytz.utc).date().isoformat()
        # Prepare filter condition based on whether shift type filtering is enabled
        filter_condition: dict[str, t.Any]
        if FIND_FOR_CURRENT_SHIFT_TYPE_ENABLED:
            filter_condition = {
                "and": [
                    {"property": "Date", "date": {"equals": today}},
                    {
                        "property": FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_NAME,
                        "select": {"equals": FIND_FOR_CURRENT_SHIFT_TYPE_ATTRIBUTE_VALUE},
                    },
                ],
            }
        else:
            filter_condition = {"property": "Date", "date": {"equals": today}}

        # This query assumes that only one shift exist, according filter condition. At least it takes the first one.
        try:
            resp = self.client.databases.query(
                database_id=self.shifts_db_id,
                filter=filter_condition,
                page_size=1,
            )
        except httpx.HTTPError:
            logger.exception("Failed to query Notion shifts database: %s", self.shifts_db_id)
            return None, []

        if shift_page := next(iter(resp.get("results", [])), None):  # type: ignore
            responsible = shift_page["properties"].get(SHIFT_RESPONSIBLE_ATTRIBUTE_NAME, {}).get("people", [])
            logger.info("Found shift for today: %s, responsible: %s", shift_page["id"], responsible)

            return shift_page["id"], responsible

        logger.info("No shift_page found for today's shift")
        return None, []

    def create_incident_page_from_alert(self, alert: Alert) -> None:
        """Create a new Notion page in the incidents database from an Alertmanager alert."""
        properties: dict[str, t.Any] = {
            "Name": {
                "title": [
                    {"text": {"content": "Incident (Created Automatically)"}},
                ],
            },
            "Incident Timeframe": {
                "date": {
                    "start": alert.startsAt,
                    "end": None,
                },
            },
            "AMFingerprint": {"rich_text": [{"text": {"content": alert.fingerprint}}]},
            "AMStatus": {"select": {"name": alert.notion_status}},
            "AMEventDetails": {"rich_text": [{"text": {"content": alert.model_dump_json()}}]},
        }
        # Assign responsible from Shifts if enabled
        shift_page_id, shift_responsible = self._get_shift()
        if shift_page_id:
            properties[INCIDENT_SHIFT_ATTRIBUTE_NAME] = {"relation": [{"id": shift_page_id}]}
            properties[INCIDENT_RESPONSIBLE_ATTRIBUTE_NAME] = {"people": shift_responsible}

        self.client.pages.create(
            parent={"database_id": self.incidents_db_id},
            properties=properties,
        )
        logger.info("Created new Notion page for fingerprint: %s and properties: %s", alert.fingerprint, properties)

    def handle_alert(self, event: dict[str, t.Any]) -> None:
        """Handle an Alertmanager event and update Notion accordingly."""
        try:
            event_obj = AlertmanagerEvent.model_validate(event)
        except Exception as e:
            logger.exception("Failed to parse Alertmanager event: %s, error: %s", event, e)
            return
        for alert in event_obj.alerts:
            logger.info("Processing alert: %s", alert)
            if notion_page_id := self.find_incident_page_by_fingerprint(alert.fingerprint):
                self.update_incident_status(notion_page_id, alert)
            else:
                self.create_incident_page_from_alert(alert)
        logger.info("Finished processing Alertmanager event")
