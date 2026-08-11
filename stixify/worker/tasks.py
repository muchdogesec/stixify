from datetime import UTC, datetime
import os
from pathlib import Path
import profile
import uuid
from django.utils import timezone
from stixify.web.models import Job
from stixify.web import models
from celery import chain, shared_task
from stixify.web.values.statistics import build_data_and_add_to_cache

import stix2

from stixify.worker import helpers
from django.conf import settings


POLL_INTERVAL = 1
def new_task(job: Job):
    if job.type == models.JobType.REPROCESS_FILES and (job.extra or {}).get("file_ids"):
        task = chain(
            *[
                process_post.si(job.id, file_id)
                for file_id in job.extra["file_ids"]
            ],
            job_completed_with_error.si(job.id),
        )
    else:
        task = process_post.s(job.id) | job_completed_with_error.si(job.id)
    task.apply_async(
        countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id)
    )

def create_reprocessing_job(file_ids, options: dict = None):
    file_ids = [str(file_id) for file_id in file_ids]
    options = dict(options or {})
    options.update(
        file_ids=file_ids,
        progress=dict(
            total_items=len(file_ids),
            processed_items=0,
            failed_processes=0,
            unprocessed_items=len(file_ids),
            current_file_id=None,
            current_index=None,
            stopped_early=False,
            stop_reason=None,
            errors=[],
        ),
    )
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.REPROCESS_FILES,
        file=None,
        state=models.JobState.PENDING,
        extra=options,
    )
    new_task(job)
    return job

@shared_task
def process_post(job_id, file_id=None, *args):
    from stixify.worker.process_post import process_post_impl

    return process_post_impl(job_id, file_id, *args)


@shared_task
def job_completed_with_error(job_id):
    job = Job.objects.get(pk=job_id)
    state = models.JobState.COMPLETED
    if job.type == models.JobType.REPROCESS_FILES and (job.extra or {}).get("progress"):
        progress = job.extra["progress"]
        progress["current_file_id"] = None
        progress["current_index"] = None
        progress["unprocessed_items"] = max(
            0,
            progress["total_items"]
            - progress["processed_items"]
            - progress["failed_processes"],
        )
        if progress["failed_processes"]:
            job.error = (
                f"failed to reprocess {progress['failed_processes']} file(s)"
            )
    if job.error:
        state = models.JobState.FAILED
        if job.type == models.JobType.IMPORT_FILE:
            job.file and job.file.delete()
    Job.objects.filter(pk=job_id).update(
        state=state,
        error=job.error,
        extra=job.extra,
        completion_time=datetime.now(UTC),
    )

from celery import signals


@signals.worker_ready.connect
def refresh_statistics_when_program_starts(**kwargs):
    auto_refresh_statistics_data.delay()

@shared_task
def update_knowledgebase(job_id):
    job = models.Job.objects.get(pk=job_id)
    try:
        helpers.run_on_collections(job, job.extra["knowledgebase"])
    except Exception as e:
        job.error = str(e)
    job.save(update_fields=["error"])


@shared_task
def auto_refresh_statistics_data():
    build_data_and_add_to_cache(timezone.now())
