import json
import os
import sys
from pathlib import Path

from decouple import AutoConfig

BASE_DIR = Path(__file__).parent.parent
config = AutoConfig(search_path=BASE_DIR.joinpath("config"))

# Common settings
GCP_PROJECT_ID = config("GCP_PROJECT_ID")
DB_TIMEZONE = config("DB_TIMEZONE", default="Europe/London")

# If not in Google Cloud, load local environment variables from .env
if not (os.getenv("GAE_ENV") or os.getenv("K_SERVICE")):  # pragma: nocover
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config("GOOGLE_APPLICATION_CREDENTIALS", "")

if "pytest" in sys.argv[0]:  # Don't try to send logs to GCP in tests
    GCP_LOGGING = False
else:  # pragma: nocover
    GCP_LOGGING = config("GCP_LOGGING", cast=bool, default="true")


# CSFU settings
CSFU_PUBSUB_TOPIC = config("EVENTS_PUBSUB_TOPIC")
CSFU_HTTP_HEADER_NAME = config("CSFU_HTTP_HEADER_NAME", default="X-SECRET")
CSFU_HTTP_HEADER_VALUE = config("CSFU_HTTP_HEADER_VALUE")
CSFU_TARGETS = config("CSFU_TARGETS")
CSFU_TARGET_TIMEOUT = config("CSFU_TARGET_TIMEOUT", default="10", cast=int)
CSFU_WEBHOOK_URL = config("CSFU_WEBHOOK_URL")
CSFU_WEBHOOK_HEADERS = config("CSFU_WEBHOOK_HEADERS", default="{}", cast=json.loads)
CSFU_WEBHOOK_RETRY_ATTEMPTS = config("CSFU_WEBHOOK_RETRY_ATTEMPTS", default="1", cast=int)
CSFU_WEBHOOK_RETRY_WAIT = config("CSFU_WEBHOOK_RETRY_WAIT", default="1", cast=int)
CSFU_WEBHOOK_TIMEOUT = config("CSFU_WEBHOOK_TIMEOUT", default="10", cast=int)
CSFU_SNAPSHOTS_KEEP_LAST_DAYS = config("CSFU_SNAPSHOTS_KEEP_LAST_DAYS", default="15", cast=int)
CSFU_PROXY = config("CSFU_PROXY", default=None)  # http://login:password@address:port
