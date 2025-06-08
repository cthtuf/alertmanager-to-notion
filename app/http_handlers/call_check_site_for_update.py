import json
import logging

import flask
from google.cloud import pubsub_v1  # type: ignore
from python_settings import settings

logger = logging.getLogger("http_csfu")
http_csfu_bp = flask.Blueprint("http_csfu", __name__)


@http_csfu_bp.before_request
def check_secret_header() -> tuple[flask.Response, int] | None:
    """Check Auth header."""
    if (
        not (secret := flask.request.headers.get(settings.CSFU_HTTP_HEADER_NAME))
        and not (secret := flask.request.args.get(settings.CSFU_HTTP_HEADER_NAME))
    ) or secret != settings.CSFU_HTTP_HEADER_VALUE:
        logger.warning(f"Invalid or missing {settings.CSFU_HTTP_HEADER_NAME} header or query param")
        return flask.jsonify({"error": "Unauthorized"}), 401

    return None


@http_csfu_bp.route("/<path:site_url>", methods=["POST"])
def call_event(site_url: str) -> tuple[flask.Response, int]:
    """Create pubsub event to check site update."""
    # Check if site url in config
    config_urls = tuple(t["url"] for t in json.loads(settings.CSFU_TARGETS)["targets"])
    if site_url not in config_urls:
        return flask.jsonify({"error": "url not found"}), 404

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, settings.CSFU_PUBSUB_TOPIC)
    message_data = json.dumps({"url": site_url}).encode("utf-8")
    try:
        future = publisher.publish(topic_path, data=message_data)
        message_id = future.result()
        logger.info("Called event, message_id=%s", message_id)
        return flask.jsonify({"message_id": message_id}), 202
    except Exception as e:
        logger.exception("Server Error: %s", e)
        return flask.jsonify({"error": "Server Error"}), 500
