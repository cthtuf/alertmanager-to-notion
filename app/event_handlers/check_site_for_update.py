import typing as t

import dataclasses as dc
import difflib
import json
import logging
from datetime import datetime, timedelta

import fireo
import pytz
import requests
from app.base import BaseHandler
from app.models import WebsiteContent
from python_settings import settings
from tenacity import (
    after_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

if t.TYPE_CHECKING:
    from google.cloud.functions_v1.context import Context  # pragma: nocover

logger = logging.getLogger("check-site-for-update")


@dc.dataclass(frozen=True)
class Target:
    """Target to check."""

    url: str
    phrase_to_find: str
    custom_headers: dict[str, t.Any] | None = None


class CheckSiteForUpdate(BaseHandler):
    """Handler for checking websites on changes."""

    def __init__(self, event: dict[str, t.Any], context: "Context") -> None:
        """
        Init handler, set params.

        CSFU_TARGETS format must be:
        {"targets": [{"url": "https://example.com", "phrase_to_find": "phrase"}]}.
        """
        self.targets: list[Target] = [
            Target(
                url=v["url"],
                phrase_to_find=v["phrase_to_find"],
                custom_headers=v.get("custom_headers", None),
            )
            for v in json.loads(settings.CSFU_TARGETS)["targets"]
        ]
        self.webhook_url: str = settings.CSFU_WEBHOOK_URL
        self.webhook_headers: dict[str, str] = settings.CSFU_WEBHOOK_HEADERS

    def __call__(self) -> None:
        """Execute handler."""
        for target in self.targets:
            try:
                self.check_website(target)
            except Exception:
                logger.exception("Error on check_website for url=%s", target.url)

        self.cleanup_snapshots()

    @retry(
        retry=retry_if_exception_type(requests.HTTPError),
        stop=stop_after_attempt(settings.CSFU_WEBHOOK_RETRY_ATTEMPTS),
        wait=wait_fixed(settings.CSFU_WEBHOOK_RETRY_WAIT),
        after=after_log(logger, logging.WARNING),
        reraise=True,
    )
    def send_webhook(self, phrase: str, line: str) -> None:
        """Send message to remote handler."""
        logger.info("Send webhook for url=%s, that phrase=%s found in line=%s", self.webhook_url, phrase, line)
        data = {"message": f'Phrase "{phrase}" found in content. Line: {line}'}
        response = requests.post(
            self.webhook_url,
            headers=self.webhook_headers,
            json=data,
            timeout=settings.CSFU_WEBHOOK_TIMEOUT,
        )
        logger.info("Webhook response with status=%s and content=%s", response.status_code, response.content)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception(
                "Error on request to webhook with data: %s, response.content=%s",
                data,
                response.content,
            )
            raise

    def save_snapshot(self, target: Target, content: str, diff: list[str]) -> None:
        """Save last content in database."""
        WebsiteContent(url=target.url, content_snapshot=content, diff="\n".join(diff)).save()

    def check_diff(self, target: Target, new_content: str, last_content: str) -> list[str]:
        """Check diff between new and old content. Send webhook if phrase to find has been found in diff."""
        diff = list(difflib.unified_diff(last_content.splitlines(), new_content.splitlines()))
        for line in diff:
            # Look for lines that were added (start with '+') and do not include lines starting with '+++'
            if line.startswith("+") and not line.startswith("+++"):
                # Check if the phrase appears in the added content
                if target.phrase_to_find in line:
                    # Send POST request to the webhook URL for each new entry
                    self.send_webhook(target.phrase_to_find, line)
                    logger.info("Found phrase to find in %s", line)
                    break
        else:
            logger.info("No diff found for %s", target.url)

        return diff

    def _get_proxy(self) -> dict[str, str] | None:
        """Get proxy."""
        return (
            {
                "http": settings.CSFU_PROXY,
                "https": settings.CSFU_PROXY,
            }
            if settings.CSFU_PROXY
            else None
        )

    def get_website_content(self, target: Target) -> str:
        """Get website content."""
        logger.info("Getting website content for url=%s with proxy: %s", target.url, settings.CSFU_PROXY)
        with requests.Session() as session:
            response = session.get(
                target.url,
                headers=target.custom_headers,
                timeout=settings.CSFU_TARGET_TIMEOUT,
                proxies=self._get_proxy(),
                verify=False,
            )
        try:
            response.raise_for_status()
        except requests.RequestException as e:
            raise requests.RequestException(  # let's add some details about this error
                f"Can't get data for url={target.url}, response.content={response.content.decode()}",
            ) from e

        return response.content.decode()

    def check_website(self, target: Target) -> None:
        """Check website on changes."""
        new_content = self.get_website_content(target)
        # Retrieve previous snapshot from Firestore
        last_check = WebsiteContent.collection.filter("url", "==", target.url).order("-timestamp").get()
        last_content = getattr(last_check, "content_snapshot", "")

        # Check a diff between the current and previous content
        diff = self.check_diff(target, new_content, last_content)

        # Save last content
        self.save_snapshot(target, new_content, diff)

    def cleanup_snapshots(self) -> None:
        """Remove old website snapshots."""
        batch = fireo.batch()
        WebsiteContent.collection.filter(
            "timestamp",
            "<=",
            datetime.now(pytz.timezone(settings.DB_TIMEZONE)) - timedelta(days=settings.CSFU_SNAPSHOTS_KEEP_LAST_DAYS),
        ).batch(batch).delete()
        batch.commit()
