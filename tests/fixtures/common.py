import pytest
from python_settings import settings


@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    """Replace settings variables for tests."""
    settings.ENVIRONMENT = "TESTING"
    settings.GCP_LOGGING = False


@pytest.fixture
def alert_payload():
    """Fixture for a sample Alertmanager event payload."""
    return {
        "receiver": "default/notion-incidents/notion-webhook-receiver",
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": "HighMemoryUtilization",
                    "namespace": "default",
                    "pod": "celery-worker-9b56786b8-7njwj",
                    "prometheus": "prometheus/prometheus-grafana-kube-pr-prometheus",
                    "severity": "WARNING",
                },
                "annotations": {
                    "description": "Pod celery-worker-9b56786b8-7njwj is using more than 80% of its memory limit.",
                    "summary": "Pod memory usage is high (93.73855590820312%) for pod celery-worker-9b56786b8-7njwj",
                },
                "startsAt": "2025-06-10T23:15:15.277Z",
                "endsAt": "2025-06-11T19:44:45.277Z",
                "generatorURL": "http://prometheus-grafana-kube-pr-prometheus.prometheus:9090/...",
                "fingerprint": "26270adf29eda488",
            },
        ],
        "groupLabels": {"pod": "celery-worker-9b56786b8-7njwj"},
        "commonLabels": {
            "alertname": "HighMemoryUtilization",
            "namespace": "default",
            "pod": "celery-worker-9b56786b8-7njwj",
            "prometheus": "prometheus/prometheus-grafana-kube-pr-prometheus",
            "severity": "WARNING",
        },
        "commonAnnotations": {
            "description": "Pod celery-worker-9b56786b8-7njwj is using more than 80% of its memory limit.",
            "summary": "Pod memory usage is high (93.73855590820312%) for pod celery-worker-9b56786b8-7njwj",
        },
        "externalURL": "http://prometheus-grafana-kube-pr-alertmanager.prometheus:9093",
        "version": "4",
        "groupKey": '{}/{namespace="default",severity=~"CRITICAL|WARNING"}:{pod="celery-worker-9b56786b8-7njwj"}',
        "truncatedAlerts": 0,
    }
