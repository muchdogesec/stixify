import logging
import uuid
from billiard.einfo import ExceptionWithTraceback
from django.db import transaction
from django.utils import timezone
from stixify.web.models import Job
from stixify.web import models
from celery import Task, chain, shared_task, signals
from celery.exceptions import TimeLimitExceeded, WorkerLostError
from celery.worker.request import Request
from stixify.web.values.statistics import build_data_and_add_to_cache

from stixify.worker import helpers


POLL_INTERVAL = 1
TERMINAL_STATES = (
    models.JobState.COMPLETED, models.JobState.FAILED, models.JobState.CANCELED,
)


def finish_job(job_id, error=None):
    """Persist completion before attempting cleanup of external resources."""
    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)
        if job.state in TERMINAL_STATES and job.completion_time is not None:
            return
        if error:
            job.error = job.error or error
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
            if error and progress["unprocessed_items"]:
                progress["stopped_early"] = True
                progress["stop_reason"] = "task_failed"
            elif progress["failed_processes"]:
                job.error = f"failed to reprocess {progress['failed_processes']} file(s)"
        job.state = models.JobState.FAILED if job.error else models.JobState.COMPLETED
        job.completion_time = timezone.now()
        job.save(update_fields=["state", "error", "extra", "completion_time"])

    if job.state == models.JobState.FAILED and job.type == models.JobType.IMPORT_FILE:
        try:
            if job.file_id:
                with transaction.atomic():
                    job.file.delete()
        except Exception:
            logging.exception("Failed to clean up file for job %s", job_id)


def record_task_failure(args, kwargs, exception):
    job_id = args[0] if args else (kwargs or {}).get("job_id")
    if job_id is None:
        return
    try:
        finish_job(job_id, f"task failed: {str(exception) or type(exception).__name__}")
    except Job.DoesNotExist:
        logging.warning("Job %s no longer exists", job_id)
    except Exception:
        logging.exception("Failed to record failure for job %s", job_id)


class JobRequest(Request):
    """Record failures that kill a prefork child before its task hooks run."""

    def on_failure(self, exc_info, send_failed_event=True, return_ok=False):
        try:
            return super().on_failure(exc_info, send_failed_event, return_ok)
        finally:
            exception = exc_info.exception
            if isinstance(exception, ExceptionWithTraceback):
                exception = exception.exc
            if isinstance(exception, (WorkerLostError, TimeLimitExceeded)):
                record_task_failure(self.args, self.kwargs, exception)

    def on_timeout(self, soft, timeout):
        try:
            return super().on_timeout(soft, timeout)
        finally:
            if not soft:
                record_task_failure(self.args, self.kwargs, TimeLimitExceeded(timeout))


class JobTask(Task):
    Request = JobRequest

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        record_task_failure(args, kwargs, exc)


def new_task(job: Job):
    if job.type == models.JobType.REPROCESS_FILES and (job.extra or {}).get("file_ids"):
        task = chain(
            *[
                process_post.si(job.id, file_id)
                for file_id in job.extra["file_ids"]
            ],
        )
    else:
        task = process_post.si(job.id)
    try:
        task.apply_async(
            countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id),
        )
    except Exception as exc:
        record_task_failure((job.id,), {}, exc)
        raise

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

@shared_task(base=JobTask)
def process_post(job_id, file_id=None, *args):
    from stixify.worker.process_post import process_post_impl

    return process_post_impl(job_id, file_id, *args)


@shared_task(base=JobTask)
def job_completed_with_error(job_id):
    finish_job(job_id)


@signals.task_internal_error.connect
def job_task_internal_error(sender, args=None, kwargs=None, exception=None, **extra):
    # This includes broker failures when Celery publishes the next file in a chain.
    if isinstance(sender, JobTask):
        record_task_failure(args, kwargs, exception)


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
