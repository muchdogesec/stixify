import pytest
from tests.utils import Transport
from unittest.mock import patch
import uuid

from stixify.classifier.models import Cluster, DocumentEmbedding


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


@pytest.mark.django_db
def test_file_filter_by_topic_id(client, more_files, api_schema):
    """Test filtering files by topic_id"""
    # Create embeddings for the files
    file1, file2, file3 = more_files
    
    emb1 = DocumentEmbedding.objects.create(
        id=file1.id,
        text="Test embedding 1",
        embedding=[1.0] + [0.0] * 511,
    )
    emb2 = DocumentEmbedding.objects.create(
        id=file2.id,
        text="Test embedding 2",
        embedding=[0.0, 1.0] + [0.0] * 510,
    )
    emb3 = DocumentEmbedding.objects.create(
        id=file3.id,
        text="Test embedding 3",
        embedding=[0.0, 0.0, 1.0] + [0.0] * 509,
    )
    
    file1.embedding = emb1
    file1.save()
    file2.embedding = emb2
    file2.save()
    file3.embedding = emb3
    file3.save()
    
    # Create clusters
    cluster1_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    cluster2_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    
    cluster1 = Cluster.objects.create(
        id=cluster1_id,
        label="Test Cluster 1",
        description="First test cluster",
    )
    cluster1.members.set([emb1, emb2])
    
    cluster2 = Cluster.objects.create(
        id=cluster2_id,
        label="Test Cluster 2",
        description="Second test cluster",
    )
    cluster2.members.set([emb3])
    
    # Test filter by cluster1_id - should return file1 and file2
    resp = client.get(f"/api/v1/files/?topic_id={cluster1_id}")
    assert resp.status_code == 200
    file_ids = {f["id"] for f in resp.data["files"]}
    assert file_ids == {str(file1.id), str(file2.id)}
    api_schema["/api/v1/files/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )
    
    # Test filter by cluster2_id - should return only file3
    resp = client.get(f"/api/v1/files/?topic_id={cluster2_id}")
    assert resp.status_code == 200
    file_ids = {f["id"] for f in resp.data["files"]}
    assert file_ids == {str(file3.id)}
    api_schema["/api/v1/files/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )
    
    # Test filter by non-existent cluster - should return empty
    non_existent_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    resp = client.get(f"/api/v1/files/?topic_id={non_existent_id}")
    assert resp.status_code == 200
    assert resp.data["files"] == []
    api_schema["/api/v1/files/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_file_filter_by_topic_id_without_embedding(client, more_files, api_schema):
    """Test that files without embeddings are not returned when filtering by topic_id"""
    cluster_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    cluster = Cluster.objects.create(
        id=cluster_id,
        label="Empty Cluster",
        description="Cluster with no members",
    )
    
    # Query with a cluster that has no members
    resp = client.get(f"/api/v1/files/?topic_id={cluster_id}")
    assert resp.status_code == 200
    assert resp.data["files"] == []
    api_schema["/api/v1/files/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )