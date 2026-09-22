import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from billiard.einfo import ExceptionWithTraceback
from celery.app.trace import build_tracer
from celery.canvas import Signature
from celery.exceptions import WorkerLostError
from celery.worker.request import Request

from stixify.worker.tasks import process_post
from stixify.worker import tasks
from stixify.web import models


def test_process_post_delegates_to_process_post_impl(monkeypatch):
    process_post_impl = Mock(return_value="job-id")
    process_post_module = ModuleType("stixify.worker.process_post")
    process_post_module.process_post_impl = process_post_impl
    monkeypatch.setitem(
        sys.modules, "stixify.worker.process_post", process_post_module
    )

    assert process_post.run("job-id", "file-id", "extra") == "job-id"
    process_post_impl.assert_called_once_with("job-id", "file-id", "extra")
    assert process_post.name == "stixify.worker.tasks.process_post"


def job_request(job_id):
    request = object.__new__(tasks.JobRequest)
    request._args = (job_id,)
    request._kwargs = {}
    return request


@pytest.mark.django_db
@pytest.mark.parametrize("wrapped", [False, True])
def test_worker_loss_records_failure(stixify_job, wrapped):
    stixify_job.type = models.JobType.REPROCESS_FILES
    stixify_job.save(update_fields=["type"])
    exception = WorkerLostError("worker exited unexpectedly")
    if wrapped:
        exception = ExceptionWithTraceback(exception, "traceback")
    with patch.object(Request, "on_failure"):
        job_request(stixify_job.id).on_failure(SimpleNamespace(exception=exception))

    stixify_job.refresh_from_db()
    assert stixify_job.state == models.JobState.FAILED
    assert stixify_job.completion_time is not None
    assert "worker exited unexpectedly" in stixify_job.error


@pytest.mark.django_db
@pytest.mark.parametrize("soft", [False, True])
def test_worker_timeout_records_only_hard_failure(stixify_job, soft):
    stixify_job.type = models.JobType.REPROCESS_FILES
    stixify_job.save(update_fields=["type"])
    with patch.object(Request, "on_timeout"):
        job_request(stixify_job.id).on_timeout(soft, 300)

    stixify_job.refresh_from_db()
    if soft:
        assert stixify_job.state == models.JobState.PENDING
        assert stixify_job.completion_time is None
    else:
        assert stixify_job.state == models.JobState.FAILED
        assert stixify_job.completion_time is not None
        assert "300" in stixify_job.error


@pytest.mark.django_db
def test_chain_publish_failure_records_terminal_status(stixify_job):
    from stixify.worker.celery import app

    stixify_job.type = models.JobType.REPROCESS_FILES
    stixify_job.save(update_fields=["type"])
    tracer = build_tracer(process_post.name, process_post, app=app, eager=False)
    task_id = "2704dd88-54a1-4e49-b577-96e8d266ce38"
    request = {
        "id": task_id,
        "chain": [process_post.si(stixify_job.id, stixify_job.file_id)],
    }
    with (
        patch("stixify.worker.process_post.process_post_impl", return_value=stixify_job.id),
        patch.object(Signature, "apply_async", side_effect=ConnectionError("broker offline")),
        pytest.warns(RuntimeWarning, match="Exception raised outside body"),
    ):
        tracer(task_id, (stixify_job.id,), {}, request)

    stixify_job.refresh_from_db()
    assert stixify_job.state == models.JobState.FAILED
    assert stixify_job.completion_time is not None
    assert "broker offline" in stixify_job.error
