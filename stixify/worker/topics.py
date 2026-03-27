
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging, typing
from django.conf import settings
from stixify.classifier import tasks as classifier_tasks
from celery import shared_task
from stixify.web import models
from django.utils import timezone

if typing.TYPE_CHECKING:
    from stixify import settings


def _build_topic_embedding_for_file(file: models.File, force=False, include_non_incident=False):
    try:
        file.create_embedding(
            force=force,
            include_non_incident=include_non_incident,
        )
        if file.embedding_id:
            return "processed", None
        return "failed", f"embedding not created for file {file.pk}"
    except Exception:
        logging.exception("embedding build failed for file %s", file.pk)
        return "failed", f"embedding build failed for file {file.pk}"


def run_topic_embeddings_job(
    job_id,
    force=False,
    workers=settings.CLASSIFIER_CONCURRENCY,
    include_non_incident=False,
):
    job = models.Job.objects.get(pk=job_id)
    if not isinstance(job.extra, dict):
        job.extra = {}
    job.extra.setdefault("processed_items", 0)
    job.extra.setdefault("failed_processes", 0)
    job.extra.setdefault("errors", [])
    try:
        qs = models.File.objects.all()
        if not include_non_incident:
            qs = qs.filter(ai_describes_incident=True)

        if not force:
            qs = qs.filter(embedding__isnull=True)
        if not qs.count():
            job.state = models.JobState.COMPLETED
            job.save(update_fields=["state"])
            return

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _build_topic_embedding_for_file,
                    file,
                    force,
                    include_non_incident,
                ): file.pk
                for file in qs
            }
            for future in as_completed(futures):
                status, msg = future.result()
                if status == "processed":
                    job.extra["processed_items"] += 1
                elif status == "failed":
                    job.extra["failed_processes"] += 1
                    if msg:
                        job.extra["errors"].append(msg)
                else:
                    logging.error("unexpected status %s for file %s", status, futures[future])
                job.save(update_fields=["extra"])
        if job.extra["failed_processes"] and job.extra["processed_items"] == 0:
            job.state = models.JobState.FAILED
        else:
            job.state = models.JobState.COMPLETED
        job.save(update_fields=["state"])
    except Exception as e:
        logging.exception("topic embedding task failed")
        job.extra["errors"].append(str(e))
        job.state = models.JobState.FAILED
        job.save(update_fields=["state"])
    finally:
        job.completion_time = timezone.now()
        job.save(update_fields=["extra", "completion_time"])

def run_topic_clusters_job(job_id, force=False):
    job = models.Job.objects.get(pk=job_id)
    try:
        classifier_tasks.run_clustering(
            force=force,
            workers=settings.CLASSIFIER_CONCURRENCY,
        )
        job.state = models.JobState.COMPLETED
    except Exception as e:
        logging.exception("topic cluster task failed")
        job.error = str(e)
        job.state = models.JobState.FAILED
    finally:
        job.completion_time = timezone.now()
        job.save(update_fields=["extra", "completion_time", "error", "state"])


@shared_task
def build_topic_clusters(job_id, force=False):
    run_topic_clusters_job(job_id, force=force)
