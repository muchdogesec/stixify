from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import profile
import time
import uuid
from django.utils import timezone
from txt2stix import txt2stixBundler
from stixify.web.models import Job, File
from stixify.web import models
from celery import chain, shared_task
from dogesec_commons.stixifier.stixifier import StixifyProcessor, ReportProperties
from dogesec_commons.stixifier.models import Profile
from stixify.web.values.statistics import build_data_and_add_to_cache

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.core.files.base import File as DjangoFile
from django.core.files.base import File as DjangoFile
from django.db import transaction
from django.core.cache import cache
import stix2

from stixify.worker import helpers, pdf_converter
from django.conf import settings
from txt2stix.txt2stix import Txt2StixData


POLL_INTERVAL = 1
ARANGO_UPLOAD_COUNTER_KEY = "arango_upload_active_count"
MAX_CONCURRENT_UPLOADS = 1
LOCK_TIMEOUT = 300


def acquire_upload_lock(job_id, wait_timeout=LOCK_TIMEOUT):
    lock_key = f"arango_upload_lock:{job_id}"
    logging.info(f"Attempting to acquire upload lock: {lock_key}")
    lock_acquired_at = cache.get(lock_key)

    if lock_acquired_at is not None:
        raise RuntimeError(f"Upload lock already held for job {job_id}")

    start_time = time.time()
    while True:
        active_count = cache.get(ARANGO_UPLOAD_COUNTER_KEY, 0)
        if active_count < MAX_CONCURRENT_UPLOADS:
            cache.set(ARANGO_UPLOAD_COUNTER_KEY, active_count + 1, LOCK_TIMEOUT)
            cache.set(lock_key, time.time(), LOCK_TIMEOUT)
            logging.info(f"Acquired upload lock for job {job_id} (active: {active_count + 1}/{MAX_CONCURRENT_UPLOADS})")
            return

        if time.time() - start_time > wait_timeout:
            raise TimeoutError(f"Timeout waiting for arango upload slot after {wait_timeout}s")

        time.sleep(0.1)


def release_upload_lock(job_id):
    lock_key = f"arango_upload_lock:{job_id}"
    if cache.get(lock_key) is not None:
        cache.delete(lock_key)
        active_count = cache.get(ARANGO_UPLOAD_COUNTER_KEY, 0)
        if active_count > 0:
            cache.set(ARANGO_UPLOAD_COUNTER_KEY, active_count - 1, LOCK_TIMEOUT)
        logging.info(f"Released upload lock for job {job_id} (active: {max(0, active_count - 1)}/{MAX_CONCURRENT_UPLOADS})")


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

def _process_file(processor, job, file):
    skip_extraction = bool((job.extra or {}).get("skip_extraction"))
    is_reprocess = job.type == models.JobType.REPROCESS_FILES

    if is_reprocess and skip_extraction:
        processor.output_md = file.markdown_file.open().read().decode()
        if not file.txt2stix_data:
            raise Exception("no existing extraction data to use for reprocess with skip_extraction=true")
        txt2stix_data = Txt2StixData.model_validate(file.txt2stix_data)
        processor.txt2stix(txt2stix_data)
    else:
        logging.info(f"running file2txt on {processor.task_name}")
        processor.file2txt()
        logging.info(f"running txt2stix on {processor.task_name}")
        processor.txt2stix()

    processor.write_bundle(processor.bundler)


def _object_value_backup(file_id):
    return list(
        models.ObjectValue.objects.filter(file_id=file_id).values(
            "id",
            "stix_id",
            "type",
            "knowledgebase",
            "values",
            "created",
            "modified",
            "is_dupe",
        )
    )


def _restore_object_values(file_id, backup):
    models.ObjectValue.objects.filter(file_id=file_id).delete()
    models.ObjectValue.objects.bulk_create(
        [models.ObjectValue(file_id=file_id, **values) for values in backup]
    )


def _update_reprocess_progress(job, file_id, error=None):
    progress = job.extra["progress"]
    if error is None:
        progress["processed_items"] += 1
    else:
        progress["failed_processes"] += 1
        progress["errors"].append(
            {"file_id": str(file_id), "message": error}
        )
        if progress["failed_processes"] >= settings.REPROCESS_MAX_FAILED_PROCESSES:
            progress["stopped_early"] = True
            progress["stop_reason"] = "failure_limit_reached"
    progress["unprocessed_items"] = max(
        0,
        progress["total_items"]
        - progress["processed_items"]
        - progress["failed_processes"],
    )


@shared_task
def process_post(job_id, file_id=None, *args):
    job = Job.objects.get(id=job_id)
    detached_reprocess = (
        job.type == models.JobType.REPROCESS_FILES and file_id is not None
    )
    if detached_reprocess:
        progress = job.extra["progress"]
        if progress["failed_processes"] >= settings.REPROCESS_MAX_FAILED_PROCESSES:
            return job_id
        progress["current_file_id"] = str(file_id)
        progress["current_index"] = (
            progress["processed_items"] + progress["failed_processes"]
        )
        file = None
    else:
        file = job.file
    object_values_backup = None
    try:
        if detached_reprocess:
            file = File.objects.get(pk=file_id)
        job.state = models.JobState.PROCESSING
        job.save()
        processing_profile = file.profile
        if job.type == models.JobType.REPROCESS_FILES and (job.extra or {}).get(
            "profile_id"
        ):
            processing_profile = Profile.objects.get(pk=job.extra["profile_id"])
        processor = StixifyProcessor(
            file.process_file,
            processing_profile,
            job_id=job.id,
            file2txt_mode=file.process_mode,
            report_id=file.id,
        )
        external_refs = [
            dict(
                source_name="stixify_profile_id",
                external_id=str(processing_profile.id),
            )
        ]
        for source in file.sources or []:
            source_ref = dict(source_name="stixify_source")
            if source.startswith("http://") or source.startswith("https://"):
                source_ref.update(url=source)
            else:
                source_ref.update(description=source)
            external_refs.append(source_ref)

        report_props = ReportProperties(
            name=file.name,
            identity=file.identity.identity,
            tlp_level=file.tlp_level,
            confidence=file.confidence,
            labels=file.labels,
            created=file.created,
            kwargs=dict(
                external_references=external_refs,
                admiralty_source_reliability=file.admiralty_source_reliability,
                admiralty_information_credibility=file.admiralty_information_credibility,
                pap_level=file.pap_level,
            ),
        )
        processor.setup(
            report_prop=report_props, extra=dict(_stixify_file_id=str(file.id))
        )

        _process_file(processor, job, file)

        if job.type == models.JobType.REPROCESS_FILES:
            object_values_backup = _object_value_backup(file.id)
        models.ObjectValue.objects.filter(file_id=file.id).delete()

        acquire_upload_lock(job.id)
        try:
            logging.info(f"uploading {processor.task_name} to arangodb via stix2arango")
            processor.upload_to_arango()
        finally:
            release_upload_lock(job.id)

        with transaction.atomic():
            new_profile_id = (job.extra or {}).get("profile_id")
            if new_profile_id:
                file.profile_id = new_profile_id
                file.save(update_fields=["profile"])
            file.set_txt2stix_data(processor.txt2stix_data)
            file.create_embedding(include_non_incident=settings.CREATE_EMBEDDING_INCLUDE_NON_INCIDENT)

            if job.type == models.JobType.IMPORT_FILE:
                file.markdown_file.save("markdown.md", processor.md_file.open(), save=True)
                models.FileImage.objects.filter(report=file).delete()

                for image in processor.md_images:
                    models.FileImage.objects.create(
                        report=file, file=DjangoFile(image, image.name), name=image.name
                    )
                if processing_profile.generate_pdf:
                    converted_file_path = processor.tmpdir / "converted_pdf.pdf"
                    pdf_converter.make_conversion(processor.filename, converted_file_path)
                    file.pdf_file.save(
                        converted_file_path.name, open(converted_file_path, mode="rb")
                    )
                file.save(update_fields=['markdown_file', 'pdf_file'])
    except Exception as e:
        error = str(e)
        job.error = "failed to process file"
        if error:
            job.error += f": {error}"
        if object_values_backup is not None and file is not None:
            try:
                _restore_object_values(file.id, object_values_backup)
            except Exception:
                logging.exception(
                    "failed to restore ObjectValue data for File %s", file.id
                )
        if detached_reprocess:
            _update_reprocess_progress(job, file_id, job.error)
        logging.error(job.error)
        logging.exception(e)
    else:
        if detached_reprocess:
            _update_reprocess_progress(job, file_id)
    job.save()
    return job_id


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
