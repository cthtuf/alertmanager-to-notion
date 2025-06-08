import typing as t

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
        self.notion_db_id = settings.AM2N_NOTION_DB_ID
        self.notion_version = "2022-06-28"

    def __call__(self) -> None:
        """Execute handler."""
        notion = NotionService(
            token=self.notion_token,
            db_id=self.notion_db_id,
            notion_version=self.notion_version,
        )
        notion.handle_alert(self.event)
