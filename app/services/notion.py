import typing as t

import logging

import requests
from pydantic import BaseModel, computed_field

logger = logging.getLogger("notion-service")

# --- Pydantic Schemas for Prometheus Alertmanager Webhook ---
# https://prometheus.io/docs/alerting/latest/notifications/#data-structures


class AlertLabels(BaseModel):
    """Labels for an alert, used to identify and categorize the alert."""

    alertname: str | None
    instance: str | None
    severity: str | None


class AlertAnnotations(BaseModel):
    """Annotations for an alert, providing additional information."""

    description: str | None
    summary: str | None


class Alert(BaseModel):
    """Represents an alert from Alertmanager."""

    status: str
    labels: AlertLabels
    annotations: AlertAnnotations
    startsAt: str
    endsAt: str
    generatorURL: str | None
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


class NotionService:
    """
    Service for interacting with Notion API to manage pages based on Alertmanager events.

    It looks at the fingerprint of alerts to find existing pages, updates their status.
    Created to working with my ITSM Incidents Template, but can be adapted for other use cases.
    """

    def __init__(self, token: str, db_id: str, notion_version: str = "2022-06-28"):
        """Set Notion API token, database ID and API version."""
        self.token = token
        self.db_id = db_id
        self.notion_version = notion_version
        self.api_url = "https://api.notion.com/v1/pages"

    def _request(self, method: str, url: str, json: dict[str, t.Any]) -> requests.Response:
        """Make a request to the Notion API with the given method and URL."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }
        resp = requests.request(method, url, headers=headers, timeout=10, json=json)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            logger.error("Notion API error [%s %s]: %s, %s", method, url, resp.text, e)
            raise
        return resp

    def find_page_by_fingerprint(self, fingerprint: str) -> str | None:
        """Search for a Notion page by its fingerprint."""
        search_url = f"https://api.notion.com/v1/databases/{self.db_id}/query"
        data = {
            "filter": {
                "property": "AMFingerprint",
                "rich_text": {"equals": fingerprint},
            },
        }
        resp = self._request("POST", search_url, json=data)
        if results := resp.json().get("results", []):
            logger.info("Fingerprint %s found in Notion, page ID: %s", fingerprint, results[0]["id"])
            return results[0]["id"]

        logger.info("Fingerprint %s not found in Notion", fingerprint)
        return None

    def update_page_status(self, page_id: str, status: str) -> None:
        """Update the status of a Notion page by its ID."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        data = {
            "properties": {
                "AMStatus": {"select": {"name": status}},
            },
        }
        self._request("PATCH", url, json=data)
        logger.info(f"Updated Notion page {page_id} with status {status}")

    def create_page_from_alert(self, alert: Alert) -> None:
        """Create a new Notion page from an Alertmanager alert."""
        url = self.api_url
        properties = {
            "AMFingerprint": {"rich_text": [{"text": {"content": alert.fingerprint}}]},
            "AMStatus": {"select": {"name": alert.notion_status}},
            # Add more fields as needed from alert
        }
        data = {
            "parent": {"database_id": self.db_id},
            "properties": properties,
        }
        self._request("POST", url, json=data)
        logger.info(f"Created new Notion page for fingerprint {alert.fingerprint}")

    def handle_alert(self, event: dict[str, t.Any]) -> None:
        """Handle an Alertmanager event, processing alerts and updating Notion."""
        try:
            event_obj = AlertmanagerEvent.model_validate(event)
        except Exception as e:
            logger.exception("Failed to parse Alertmanager event: %s, error: %s", event, e)
            return

        for alert in event_obj.alerts:
            logger.info("Processing alert: %s", alert)
            if notion_page_id := self.find_page_by_fingerprint(alert.fingerprint):
                self.update_page_status(notion_page_id, alert.notion_status)
            else:
                self.create_page_from_alert(alert)

        logger.info("Finished processing Alertmanager event")
