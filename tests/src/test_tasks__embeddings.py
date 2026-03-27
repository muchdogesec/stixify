



from unittest.mock import ANY, call, patch
import uuid, pytest

from stixify.classifier.models import DocumentEmbedding
from stixify.web import models
from stixify.worker.topics import build_topic_clusters, run_topic_clusters_job, run_topic_embeddings_job

from stixify.classifier import tasks as classifier_tasks

@pytest.mark.django_db
def test_run_topic_embeddings_job_success(more_files):
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    for f in more_files:
        f.ai_describes_incident = True
        f.embedding = None
        f.save(update_fields=["ai_describes_incident", "embedding"])

    emb = DocumentEmbedding.objects.create(
        id=more_files[0].pk,
        text="existing embedding",
        embedding=[0.0] * 512,
    )
    more_files[0].embedding = emb
    more_files[0].save(update_fields=["embedding"])

    with patch("stixify.worker.topics._build_topic_embedding_for_file", return_value=("processed", None)) as mock_build:
        run_topic_embeddings_job(job.id, force=False)

    job.refresh_from_db()
    assert mock_build.call_count == 2
    assert job.extra["processed_items"] == 2
    assert job.extra["failed_processes"] == 0
    assert job.state == models.JobState.COMPLETED
    assert job.completion_time is not None


@pytest.mark.django_db
def test_run_topic_embeddings_job_force_includes_existing(more_files):
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    for f in more_files:
        f.ai_describes_incident = True
        f.embedding = None
        f.save(update_fields=["ai_describes_incident", "embedding"])

    emb = DocumentEmbedding.objects.create(
        id=more_files[0].pk,
        text="existing embedding",
        embedding=[0.0] * 512,
    )
    more_files[0].embedding = emb
    more_files[0].save(update_fields=["embedding"])

    with patch("stixify.worker.topics._build_topic_embedding_for_file", return_value=("processed", None)) as mock_build:
        run_topic_embeddings_job(job.id, force=True)

    job.refresh_from_db()
    assert mock_build.call_count == 3
    assert job.extra["processed_items"] == 3
    assert job.state == models.JobState.COMPLETED
    assert job.completion_time is not None


@pytest.mark.django_db
def test_run_topic_embeddings_job_include_non_incident_flag(more_files):
    for i, f in enumerate(more_files):
        f.ai_describes_incident = i < 2
        f.embedding = None
        f.save(update_fields=["ai_describes_incident", "embedding"])

    job_without_flag = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    with patch("stixify.worker.topics._build_topic_embedding_for_file", return_value=("processed", None)) as mock_build:
        run_topic_embeddings_job(job_without_flag.id, force=False, include_non_incident=False)

    assert mock_build.call_count == 2 # should only process the 2 files that describe an incident
    mock_build.assert_has_calls(
        [call(ANY, False, False), call(ANY, False, False)], any_order=True
    )  # should pass False for include_non_incident
    mock_build.reset_mock()

    job_with_flag = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    with patch.object(models.File, "create_embedding") as mock_create_embedding:
        run_topic_embeddings_job(job_with_flag.id, force=False, include_non_incident=True)

    assert mock_create_embedding.call_count == 3
    mock_create_embedding.assert_has_calls([call(force=False, include_non_incident=True)] * 3, any_order=True)  # should default to False if include_non_incident is not passed


@pytest.mark.django_db
def test_run_topic_embeddings_job_include_non_incident_defaults_false(more_files):
    for i, f in enumerate(more_files):
        f.ai_describes_incident = i == 0
        f.embedding = None
        f.save(update_fields=["ai_describes_incident", "embedding"])

    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    with patch("stixify.worker.topics._build_topic_embedding_for_file", return_value=("processed", None)) as mock_build:
        run_topic_embeddings_job(job.id, force=False)

    assert mock_build.call_count == 1
    mock_build.assert_called_with(ANY, ANY, False)  # should default to False if include_non_incident is not passed

    job.refresh_from_db()
    assert job.completion_time is not None


@pytest.mark.django_db
def test_run_topic_clusters_job_success():
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_CLUSTERS,
        state=models.JobState.PROCESSING,
    )

    with patch("stixify.worker.topics.classifier_tasks.run_clustering") as mock_clustering:
        run_topic_clusters_job(job.id, force=True)

    job.refresh_from_db()
    assert mock_clustering.call_count == 1
    kwargs = mock_clustering.call_args.kwargs
    assert kwargs["force"] is True
    assert kwargs["workers"] >= 1
    assert job.state == models.JobState.COMPLETED
    assert job.completion_time is not None


@pytest.mark.django_db
def test_run_topic_clusters_job_clustering_cancelled():
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_CLUSTERS,
        state=models.JobState.PROCESSING,
    )

    with patch(
        "stixify.worker.topics.classifier_tasks.run_clustering",
        side_effect=classifier_tasks.ClusteringCancelled,
    ):
        run_topic_clusters_job(job.id, force=False)

    job.refresh_from_db()
    assert job.state == models.JobState.FAILED
    assert job.error is not None
    assert job.completion_time is not None


@pytest.mark.django_db
def test_build_topic_clusters_wrapper_passes_force():
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.BUILD_CLUSTERS,
        state=models.JobState.PROCESSING,
    )
    with patch("stixify.worker.topics.run_topic_clusters_job") as mock_runner:
        build_topic_clusters.run(job.id, force=True)
    mock_runner.assert_called_once_with(job.id, force=True)
