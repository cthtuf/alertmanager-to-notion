import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest
import pytz
import requests
from app.event_handlers.check_site_for_update import CheckSiteForUpdate, Target
from app.settings import CSFU_SNAPSHOTS_KEEP_LAST_DAYS, CSFU_WEBHOOK_URL, DB_TIMEZONE
from google.cloud.functions_v1.context import Context
from python_settings import settings


@patch("requests.post")
def test_send_webhook_success(mock_post):
    """Ensures send_webhook emit request with proper payload."""
    mock_post.return_value = MagicMock(status_code=200)
    csfu = CheckSiteForUpdate({}, Context())
    csfu.send_webhook("test_phrase", "test_line")
    mock_post.assert_called_once_with(
        CSFU_WEBHOOK_URL,
        headers=settings.CSFU_WEBHOOK_HEADERS,
        json={"message": 'Phrase "test_phrase" found in content. Line: test_line'},
        timeout=settings.CSFU_WEBHOOK_TIMEOUT,
    )


@patch("tenacity.nap.time.sleep")
@patch("requests.post")
@patch("logging.Logger.exception")
def test_send_webhook_failure(mock_logger_exception, mock_post, mock_tenacity_sleep):
    """Ensures send_webhook write a log entry on error."""
    mock_response = MagicMock(status_code=400)
    mock_response.raise_for_status.side_effect = requests.HTTPError("Error")
    mock_post.return_value = mock_response
    csfu = CheckSiteForUpdate({}, Context())
    with pytest.raises(requests.HTTPError):
        csfu.send_webhook("test_phrase", "test_line")
        mock_logger_exception.assert_called_once()


@patch("app.models.WebsiteContent.save")
def test_save_snapshot(mock_save):
    """Ensures save_snapshot would call model.save."""
    csfu = CheckSiteForUpdate({}, Context())
    target = Target(url="https://example.com", phrase_to_find="PHRASE")
    csfu.save_snapshot(target, "test_content", ["+new content", "-old content"])
    mock_save.assert_called_once()


@patch("app.event_handlers.check_site_for_update.CheckSiteForUpdate.send_webhook")
@patch("logging.Logger.info")
def test_check_diff_phrase_found(mock_logger_info, mock_send_webhook):
    """Ensures if diff found, webhook would call with proper params."""
    last_content = "This is the old content."
    new_content = "This is the old content.\nThis is the new line with PHRASE."
    csfu = CheckSiteForUpdate({}, Context())
    target = Target(url="https://example.com", phrase_to_find="PHRASE")
    csfu.check_diff(target, new_content, last_content)
    mock_send_webhook.assert_called_once_with("PHRASE", "+This is the new line with PHRASE.")
    mock_logger_info.assert_any_call("Found phrase to find in %s", "+This is the new line with PHRASE.")


@patch("app.event_handlers.check_site_for_update.CheckSiteForUpdate.send_webhook")
@patch("logging.Logger.info")
def test_check_diff_no_phrase(mock_logger_info, mock_send_webhook):
    """Ensures if diff not found, webhook would not be called."""
    last_content = "This is the old content."
    new_content = "This is the old content.\n+ This is a new line without the phrase."
    csfu = CheckSiteForUpdate({}, Context())
    target = Target(url="https://example.com", phrase_to_find="PHRASE")
    csfu.check_diff(target, new_content, last_content)
    mock_send_webhook.assert_not_called()
    mock_logger_info.assert_any_call("No diff found for %s", "https://example.com")


@patch("app.event_handlers.check_site_for_update.CheckSiteForUpdate.get_website_content")
@patch("app.event_handlers.check_site_for_update.CheckSiteForUpdate.save_snapshot")
@patch(
    "app.event_handlers.check_site_for_update.CheckSiteForUpdate.check_diff",
    return_value=["+new content", "-old content"],
)
def test_check_website(mock_check_diff, mock_save_snapshot, mock_get_content, website_content_obj):
    """Ensures check_website calls proper methods inside."""
    mock_get_content.return_value = "new content"
    csfu = CheckSiteForUpdate({}, Context())
    target = Target(url="https://example.com", phrase_to_find="PHRASE")
    csfu.check_website(target)

    mock_check_diff.assert_called_once_with(
        target,
        "new content",
        website_content_obj.content_snapshot,
    )
    mock_save_snapshot.assert_called_once_with(target, "new content", ["+new content", "-old content"])
    mock_get_content.assert_called_with(target)


@patch("app.models.WebsiteContent.collection.filter")
@patch("fireo.batch")
def test_cleanup_snapshots(mock_batch, mock_filter, mock_now):
    """Ensures cleanup_snapshots would call DB with proper params."""
    mock_batch_instance = MagicMock()
    mock_batch.return_value = mock_batch_instance
    mock_filter.return_value.batch.return_value.delete.return_value = None

    csfu = CheckSiteForUpdate({}, Context())
    csfu.cleanup_snapshots()

    mock_filter.assert_called_once_with(
        "timestamp",
        "<=",
        datetime.now(pytz.timezone(DB_TIMEZONE)) - timedelta(days=CSFU_SNAPSHOTS_KEEP_LAST_DAYS),
    )
    mock_batch_instance.commit.assert_called_once()


@patch("app.event_handlers.check_site_for_update.requests.Session")
def test_checksiteforupdate_call_no_proxy(mock_requests_session, website_content_obj):
    """Ensures handling params with list of targets properly."""
    mock_session = mock_requests_session.return_value.__enter__.return_value
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"new content"
    settings.CSFU_PROXY = None
    CheckSiteForUpdate({}, Context())()
    mock_session.get.assert_has_calls(
        [
            call(
                json.loads(settings.CSFU_TARGETS)["targets"][0]["url"],
                headers=None,
                timeout=30,
                proxies=None,
                verify=False,
            ),
        ],
    )


@patch("app.event_handlers.check_site_for_update.requests.Session")
def test_checksiteforupdate_call_with_proxy(mock_requests_session, website_content_obj):
    """Ensures handling params with list of targets properly."""
    mock_session = mock_requests_session.return_value.__enter__.return_value
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"new content"
    settings.CSFU_PROXY = "http://login:pwd@proxy-address:port"
    CheckSiteForUpdate({}, Context())()
    mock_session.get.assert_has_calls(
        [
            call(
                json.loads(settings.CSFU_TARGETS)["targets"][0]["url"],
                headers=None,
                timeout=30,
                proxies={
                    "http": "http://login:pwd@proxy-address:port",
                    "https": "http://login:pwd@proxy-address:port",
                },
                verify=False,
            ),
        ],
    )


@patch("app.event_handlers.check_site_for_update.requests.Session")
def test_checksiteforupdate_call_not_found(mock_requests_session, website_content_obj):
    """Ensures handling params with list of targets properly."""
    mock_session = mock_requests_session.return_value.__enter__.return_value
    mock_session.get.return_value.status_code = 404
    mock_session.get.return_value.content = None
    mock_session.get.return_value.raise_for_status.side_effect = requests.HTTPError()
    settings.CSFU_PROXY = None
    CheckSiteForUpdate({}, Context())()
    mock_session.get.assert_has_calls(
        [
            call(
                json.loads(settings.CSFU_TARGETS)["targets"][0]["url"],
                headers=None,
                timeout=30,
                proxies=None,
                verify=False,
            ),
        ],
    )
