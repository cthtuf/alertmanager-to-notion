import json
import logging

import flask
from google.cloud import pubsub_v1  # type: ignore
from python_settings import settings

logger = logging.getLogger("http_am2n")
http_am2n_bp = flask.Blueprint("http_am2n", __name__)


@http_am2n_bp.before_request
def check_secret_header() -> tuple[flask.Response, int] | None:
    """Check Auth header."""
    if (
        not (secret := flask.request.headers.get(settings.AM2N_HTTP_HEADER_NAME))
        and not (secret := flask.request.args.get(settings.AM2N_HTTP_HEADER_NAME))
    ) or secret != settings.AM2N_HTTP_HEADER_VALUE:
        logger.warning(f"Invalid or missing {settings.AM2N_HTTP_HEADER_NAME} header or query param")
        return flask.jsonify({"error": "Unauthorized"}), 401

    return None


@http_am2n_bp.route("/alertmanager", methods=["POST"])
def call_event() -> tuple[flask.Response, int]:
    """Create pubsub event to process Alertmanager webhook."""
    try:
        payload = flask.request.get_json(force=True)
    except Exception:
        return flask.jsonify({"error": "Invalid JSON"}), 400

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, settings.EVENTS_PUBSUB_TOPIC)
    message_data = json.dumps(payload).encode("utf-8")
    try:
        future = publisher.publish(topic_path, data=message_data)
        message_id = future.result()
        logger.info("Called event, message_id=%s", message_id)
        return flask.jsonify({"message_id": message_id}), 202
    except Exception as e:
        logger.exception("Server Error: %s", e)
        return flask.jsonify({"error": "Server Error"}), 500
