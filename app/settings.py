import logging
import os
import sys
from pathlib import Path

from decouple import AutoConfig

BASE_DIR = Path(__file__).parent.parent
config = AutoConfig(search_path=BASE_DIR.joinpath("config"))

# Common settings
GCP_PROJECT_ID = config("GCP_PROJECT_ID")
LOG_LEVEL = config("LOG_LEVEL", cast=logging.getLevelName, default=logging.INFO)

# If not in Google Cloud, load local environment variables from .env
if not (os.getenv("GAE_ENV") or os.getenv("K_SERVICE")):  # pragma: nocover
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config("GOOGLE_APPLICATION_CREDENTIALS", "")

if "pytest" in sys.argv[0]:  # Don't try to send logs to GCP in tests
    GCP_LOGGING = False
else:  # pragma: nocover
    GCP_LOGGING = config("GCP_LOGGING", cast=bool, default="true")

EVENTS_PUBSUB_TOPIC = config("EVENTS_PUBSUB_TOPIC")

# AM2N (Alertmanager to Notion) settings
AM2N_NOTION_TOKEN = config("AM2N_NOTION_TOKEN")
AM2N_NOTION_DB_ID = config("AM2N_NOTION_DB_ID")
AM2N_HTTP_HEADER_NAME = config("AM2N_HTTP_HEADER_NAME", default="X-AM2N-SECRET")
AM2N_HTTP_HEADER_VALUE = config("AM2N_HTTP_HEADER_VALUE")
