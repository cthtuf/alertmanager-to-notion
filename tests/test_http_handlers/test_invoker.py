from unittest.mock import patch

import pytest
from app import blueprints
from flask import Flask
from python_settings import settings


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
    client.environ_base["HTTP_{}".format(settings.CSFU_HTTP_HEADER_NAME.upper().replace("-", "_"))] = (
        settings.CSFU_HTTP_HEADER_VALUE
    )

    return client


def test_call_check_site_no_auth(client):
    """Test call check site without auth."""
    response = client.post("/some.website.com")
    assert response.status_code == 401, response.data
    assert response.json == {"error": "Unauthorized"}


def test_call_check_site_url_token(client):
    """Test call check site with token in url."""
    response = client.post(f"/some.website.com?{settings.CSFU_HTTP_HEADER_NAME}={settings.CSFU_HTTP_HEADER_VALUE}")
    assert response.status_code == 404, response.data
    assert response.json == {"error": "url not found"}


def test_call_check_site_wrong_site(auth_client):
    """Test call check site with wrong site."""
    response = auth_client.post("/some.website.com")
    assert response.status_code == 404, response.data
    assert response.json == {"error": "url not found"}


@patch("app.http_handlers.call_check_site_for_update.pubsub_v1.PublisherClient")
def test_call_check_site_error_during_publish(mock_publisher_client, auth_client):
    """Test call check site with error during publish."""
    mock_publisher_client.return_value.publish.side_effect = Exception("Exception1")
    response = auth_client.post("/https://example.com")
    assert response.status_code == 500, response.data
    assert response.json == {"error": "Server Error"}


@patch("app.http_handlers.call_check_site_for_update.pubsub_v1.PublisherClient")
def test_call_check_site_success(mock_publisher_client, auth_client):
    """Test call check site with success."""
    mock_publisher_client.return_value.publish.return_value.result.return_value = "message_id1"
    response = auth_client.post("/https://example.com")
    assert response.status_code == 202, response.data
    assert response.json == {"message_id": "message_id1"}
