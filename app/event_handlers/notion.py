import typing as t

import base64
import json

from python_settings import settings

from app.base import BaseHandler
from app.services.notion import NotionService

if t.TYPE_CHECKING:
    from google.cloud.functions_v1.context import Context  # pragma: nocover


class NotionHandler(BaseHandler):
    """Handler for processing Alertmanager webhooks and syncing with Notion."""

    def __init__(self, event: dict[str, t.Any], context: "Context") -> None:
        """Init handler, set params."""
        self.event = event
        self.notion_token = settings.AM2N_NOTION_TOKEN
        self.incidents_db_id = settings.AM2N_INCIDENTS_DB_ID
        self.shifts_db_id = settings.AM2N_SHIFTS_DB_ID
        self.shifts_enabled = settings.AM2N_SHIFTS_SUPPORT_ENABLED
        self.notion_version = "2022-06-28"

    def __call__(self) -> None:
        """Execute handler."""
        # Decode base64 and parse JSON
        raw_data = self.event["data"]
        decoded_data = base64.b64decode(raw_data).decode("utf-8")
        data_dict = json.loads(decoded_data)
        notion = NotionService(
            token=self.notion_token,
            incidents_db_id=self.incidents_db_id,
            shifts_db_id=self.shifts_db_id,
            shifts_enabled=self.shifts_enabled,
            notion_version=self.notion_version,
        )
        notion.handle_alert(data_dict)
