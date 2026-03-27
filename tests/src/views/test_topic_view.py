import uuid
from unittest.mock import patch

import pytest

from stixify.classifier.models import Cluster, DocumentEmbedding
from stixify.web.models import File
from stixify.web.topics import TopicDetailSerializer, TopicSerializer, TopicView
from stixify.web import models as ob_models
from dogesec_commons.utils import Pagination

from tests.utils import Transport

# ── fixtures ──────────────────────────────────────────────────────────────────

CLUSTER_1_ID = uuid.UUID("a1111111-1111-1111-1111-111111111111")
CLUSTER_2_ID = uuid.UUID("a2222222-2222-2222-2222-222222222222")

# 512-dimensional unit vectors
VEC1 = [1.0] + [0.0] * 511
VEC2 = [0.0, 1.0] + [0.0] * 510


@pytest.fixture
def posts_with_clusters(more_files):
    """Attach DocumentEmbeddings and two Clusters to the first two files."""
    file1 = more_files[0]
    file2 = more_files[1]

    emb1 = DocumentEmbedding.objects.create(
        id=file1.id, text="Iran cyber ops text", embedding=VEC1
    )
    emb2 = DocumentEmbedding.objects.create(
        id=file2.id, text="Ransomware overview text", embedding=VEC2
    )

    file1.embedding = emb1
    file1.save(update_fields=["embedding"])
    file2.embedding = emb2
    file2.save(update_fields=["embedding"])

    # cluster1 contains both files; cluster2 contains only file2
    cluster1 = Cluster.objects.create(
        id=CLUSTER_1_ID,
        label="Iran Cyber Threats",
        description="Iran-aligned cyber operations",
    )
    cluster1.members.set([emb1, emb2])

    cluster2 = Cluster.objects.create(
        id=CLUSTER_2_ID,
        label="Ransomware Campaigns",
        description="Ransomware activity overview",
    )
    cluster2.members.set([emb2])

    return [
        file1,
        file2,
        dict(
            emb1=emb1,
            emb2=emb2,
            cluster1=cluster1,
            cluster2=cluster2,
        )
    ]


# ── class-level checks ────────────────────────────────────────────────────────


def test_class_variables():
    assert TopicView.openapi_tags == ["Topics"]
    assert TopicView.lookup_url_kwarg == "topic_id"
    assert isinstance(TopicView.pagination_class, Pagination)
    assert TopicView.pagination_class.results_key == "topics"


# ── list ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_list_topics_empty(client, api_schema):
    resp = client.get("/api/v1/topics/")
    assert resp.status_code == 200
    assert resp.data["total_results_count"] == 0
    assert resp.data["topics"] == []
    api_schema["/api/v1/topics/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_list_topics(client, posts_with_clusters, api_schema):
    resp = client.get("/api/v1/topics/")
    assert resp.status_code == 200
    assert resp.data["total_results_count"] == 2
    ids = {t["id"] for t in resp.data["topics"]}
    assert ids == {str(CLUSTER_1_ID), str(CLUSTER_2_ID)}
    api_schema["/api/v1/topics/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_list_topics_posts_count(client, posts_with_clusters, api_schema):
    resp = client.get("/api/v1/topics/")
    assert resp.status_code == 200
    by_id = {t["id"]: t for t in resp.data["topics"]}
    # cluster1 has both files; cluster2 has only file2
    assert by_id[str(CLUSTER_1_ID)]["files_count"] == 2
    assert by_id[str(CLUSTER_2_ID)]["files_count"] == 1
    api_schema["/api/v1/topics/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ["label_query", "expected_ids"],
    [
        ("Iran", [CLUSTER_1_ID]),
        ("ransomware", [CLUSTER_2_ID]),
        ("Cyber", [CLUSTER_1_ID]),  # case-insensitive
        ("campaign", [CLUSTER_2_ID]),  # substring
        ("Threats Campaigns", []),  # no partial-match across words like this
    ],
)
def test_list_topics_label_filter(
    client, posts_with_clusters, api_schema, label_query, expected_ids
):
    resp = client.get("/api/v1/topics/", query_params={"label": label_query})
    assert resp.status_code == 200
    ids = {uuid.UUID(t["id"]) for t in resp.data["topics"]}
    assert ids == set(expected_ids)
    api_schema["/api/v1/topics/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_list_topics_uses_topic_serializer(client, posts_with_clusters, api_schema):
    resp = client.get("/api/v1/topics/")
    assert resp.status_code == 200
    topic = resp.data["topics"][0]
    # TopicSerializer: id, label, description, files_count
    assert set(topic.keys()) >= {"id", "label", "description", "files_count"}
    # files should NOT be present on the list response
    assert "files" not in topic
    api_schema["/api/v1/topics/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


# ── retrieve ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_retrieve_topic(client, posts_with_clusters, api_schema):
    resp = client.get(f"/api/v1/topics/{CLUSTER_1_ID}/")
    assert resp.status_code == 200
    assert resp.data["id"] == str(CLUSTER_1_ID)
    assert resp.data["label"] == "Iran Cyber Threats"
    assert resp.data["description"] == "Iran-aligned cyber operations"
    api_schema[f"/api/v1/topics/{{topic_id}}/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_retrieve_topic_post_ids(client, posts_with_clusters, api_schema):
    resp = client.get(f"/api/v1/topics/{CLUSTER_1_ID}/")
    assert resp.status_code == 200
    assert "files" in resp.data
    assert {p["id"] for p in resp.data["files"]} == {str(posts_with_clusters[0].id), str(posts_with_clusters[1].id)}
    assert set(resp.data["files"][0].keys()) == {"id", "title", "identity_id"}
    api_schema["/api/v1/topics/{topic_id}/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )

    # cluster2 only has file2
    resp2 = client.get(f"/api/v1/topics/{CLUSTER_2_ID}/")
    assert resp2.status_code == 200
    assert [p["id"] for p in resp2.data["files"]] == [str(posts_with_clusters[1].id)]
    api_schema["/api/v1/topics/{topic_id}/"]["GET"].validate_response(
        Transport.get_st_response(resp2)
    )


@pytest.mark.django_db
def test_retrieve_topic_uses_detail_serializer(client, posts_with_clusters, api_schema):
    resp = client.get(f"/api/v1/topics/{CLUSTER_1_ID}/")
    assert resp.status_code == 200
    # TopicDetailSerializer adds files with file metadata.
    assert "files" in resp.data
    assert resp.data['files_count'] == 2
    api_schema["/api/v1/topics/{topic_id}/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_retrieve_topic_not_found(client, api_schema):
    missing_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    resp = client.get(f"/api/v1/topics/{missing_id}/")
    assert resp.status_code == 404
    api_schema["/api/v1/topics/{topic_id}/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )


@pytest.mark.django_db
def test_build_clusters_action(client, celery_eager):
    with patch("stixify.worker.topics.build_topic_clusters.run") as mock_task:
        resp = client.patch("/api/v1/topics/build_clusters/")
        assert resp.status_code == 201
        data = resp.json()
        job_id = data.get("id")
        assert job_id

        job = ob_models.Job.objects.get(pk=job_id)
        assert job.type == ob_models.JobType.BUILD_CLUSTERS
        assert job.state == ob_models.JobState.PROCESSING
        mock_task.assert_called_once_with(uuid.UUID(job_id), force=False)
