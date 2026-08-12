import pytest
from django.core.cache import cache
from django.core.management import call_command

from stixify.web import models


@pytest.mark.django_db
def test_fail_incomplete_tasks(stixify_file):
    pending_job = models.Job.objects.create(file=stixify_file)
    processing_job = models.Job.objects.create(
        file=stixify_file, state=models.JobState.PROCESSING
    )
    completed_job = models.Job.objects.create(
        file=stixify_file, state=models.JobState.COMPLETED
    )
    lock_keys = [
        f"arango_upload_lock:{pending_job.id}",
        # f"arango_upload_lock:{processing_job.id}", // test that cache delete_many works with missing keys
    ]
    cache.set_many({key: "locked" for key in lock_keys})
    cache.set("arango_upload_active_count", 2)
    cache.set("unrelated", "preserved")

    call_command("fail_incomplete_tasks")

    pending_job.refresh_from_db()
    processing_job.refresh_from_db()
    completed_job.refresh_from_db()
    for job in (pending_job, processing_job):
        assert job.state == models.JobState.CANCELED
        assert job.error == "canceled automatically during restart"
        assert job.completion_time is not None
    assert completed_job.state == models.JobState.COMPLETED
    assert completed_job.error is None
    assert completed_job.completion_time is None
    assert cache.get_many(lock_keys) == {}
    assert cache.get("arango_upload_active_count") is None
    assert cache.get("unrelated") == "preserved"
