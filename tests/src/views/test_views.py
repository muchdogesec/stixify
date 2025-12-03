import pytest
from tests.utils import Transport
from unittest.mock import patch



def test_schema_view(client):
    resp = client.get('/api/schema/')
    assert resp.status_code == 200
    assert resp.headers['content-type'] == "application/vnd.oai.openapi; charset=utf-8"


def test_healthcheck(client):
    resp = client.get('/api/healthcheck/')
    assert resp.status_code == 204

def test_healthcheck_service(client, api_schema):
    resp = client.get('/api/healthcheck/service/')
    assert resp.status_code == 200
    api_schema['/api/healthcheck/service/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_sync_vulnerabilities_passes(client, api_schema, celery_eager):
    resp = client.patch("/api/v1/tasks/sync-vulnerabilities/")
    assert resp.status_code == 201
    api_schema["/api/v1/tasks/sync-vulnerabilities/"]["PATCH"].validate_response(
        Transport.get_st_response(resp)
    )
    resp_data = dict(resp.data)
    assert resp_data.pop("completion_time") != None
    assert resp_data == {
        "id": resp_data['id'],
        "file": None,
        "type": "sync-vulnerabilities",
        "state": "completed",
        "extra": {
            "document_count": 0,
            "processed_documents": 0,
            "unique_vulnerabilities": 0,
        },
        "error": None,
        "run_datetime": resp_data['run_datetime'],
    }


@pytest.mark.django_db
def test_sync_vulnerabilities_fails(client, api_schema, celery_eager):
    with patch("stixify.worker.helpers.get_vulnerabilities", side_effect=Exception("explosion!")):
        resp = client.patch("/api/v1/tasks/sync-vulnerabilities/")
    
    assert resp.status_code == 201
    api_schema["/api/v1/tasks/sync-vulnerabilities/"]["PATCH"].validate_response(
        Transport.get_st_response(resp)
    )
    resp_data = dict(resp.data)
    assert resp_data.pop("completion_time") != None
    assert resp_data == {
        "id": resp_data['id'],
        "file": None,
        "type": "sync-vulnerabilities",
        "state": "failed",
        "extra": None,
        "error": 'explosion!',
        "run_datetime": resp_data['run_datetime'],
    }