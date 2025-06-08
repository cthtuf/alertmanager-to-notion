from unittest.mock import patch

import pytest
from flask import Flask
from python_settings import settings

from app import blueprints


@pytest.fixture(scope="session")
def flask_app():
    """Flask app fixture."""
    http_app = Flask(__name__)
    for blueprint in blueprints:
        http_app.register_blueprint(blueprint)

    return http_app


@pytest.fixture
def client(flask_app):
    """Test client."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def auth_client(client):
    """Test client with auth."""
    client.environ_base["HTTP_{}".format(settings.AM2N_HTTP_HEADER_NAME.upper().replace("-", "_"))] = (
        settings.AM2N_HTTP_HEADER_VALUE
    )

    return client


def test_call_alertmanager_no_auth(client):
    """Test call alertmanager without auth."""
    response = client.post("/alertmanager")
    assert response.status_code == 401, response.data
    assert response.json == {"error": "Unauthorized"}


def test_call_alertmanager_invalid_json(auth_client):
    """Test call alertmanager with invalid JSON."""
    response = auth_client.post("/alertmanager", data="notjson", content_type="application/json")
    assert response.status_code == 400, response.data
    assert response.json == {"error": "Invalid JSON"}


@patch("app.http_handlers.call_alertmanager_to_notion.pubsub_v1.PublisherClient")
def test_call_alertmanager_error_during_publish(mock_publisher_client, auth_client):
    """Test call alertmanager with error during publish."""
    mock_publisher_client.return_value.publish.side_effect = Exception("Exception1")
    response = auth_client.post("/alertmanager", json={"alerts": []})
    assert response.status_code == 500, response.data
    assert response.json == {"error": "Server Error"}


@patch("app.http_handlers.call_alertmanager_to_notion.pubsub_v1.PublisherClient")
def test_call_alertmanager_success(mock_publisher_client, auth_client):
    """Test call alertmanager with success."""
    mock_publisher_client.return_value.publish.return_value.result.return_value = "message_id1"
    response = auth_client.post("/alertmanager", json={"alerts": []})
    assert response.status_code == 202, response.data
    assert response.json == {"message_id": "message_id1"}
