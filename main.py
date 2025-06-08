import typing as t

import logging

import google.cloud.logging
from app import blueprints, event_handlers, exceptions
from flask import Flask, Request, Response
from python_settings import settings

if t.TYPE_CHECKING:
    from google.cloud.functions_v1.context import Context

if settings.GCP_LOGGING:
    client = google.cloud.logging.Client()
    client.setup_logging()
else:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger("main")


def handle_event(event: dict[str, t.Any], context: "Context") -> None:
    """Handle event from pubsub."""
    logger.info("Handle event started")

    for handler in event_handlers:
        try:
            logger.info(f"Handle event by {handler.__name__}")
            handler(event, context)()
            logger.info(f"Finished handle event by {handler.__name__}")
        except exceptions.StopHandlingEvent:
            logger.info("Got stop handling event from handler %s", handler.__name__)
            break

    logger.info("Handle event finished")


def handle_http_request(request: Request) -> Response:
    """Handle HTTP-requests."""
    http_app = Flask(__name__)
    for blueprint in blueprints:
        http_app.register_blueprint(blueprint)

    with http_app.request_context(request.environ):
        logger.debug("Before request, req.environ=%s", request.environ)
        return http_app.full_dispatch_request()
