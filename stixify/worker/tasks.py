import logging
import os
from pathlib import Path
from stixify.web.models import Job, Profile
from stixify.web import models
from celery import shared_task
from .stixifier import StixifyProcessor, ReportProperties
from tempfile import NamedTemporaryFile
import tempfile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
import stix2
POLL_INTERVAL = 1


def new_task(job: Job, file):
    ( process_post.s(file.name, job.id) | job_completed_with_error.si(job.id)).apply_async(
        countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id)
    )


def save_file(file: InMemoryUploadedFile):
    filename = Path(file.name).name
    print("name=", file.name, filename)
    fd, filename = tempfile.mkstemp(suffix='--'+filename, prefix='file--')
    os.write(fd, file.read())
    return filename


@shared_task
def process_post(filename, job_id, *args):
    job = Job.objects.get(id=job_id)
    try:
        processor = StixifyProcessor(default_storage.open(filename), job, file2txt_mode=job.file.mode)
        report_props = ReportProperties(
            name=job.file.name,
            identity=stix2.Identity(**job.file.identity),
            tlp_level=job.file.tlp_level,
            confidence=job.file.confidence,
            labels=job.file.labels,
            created=job.file.created,
        )
        processor.setup(report_prop=report_props, extra=dict(_stixify_file_id=str(job.file.id)))
        job.file.report_id = processor.process()
        job.file.save()
    except Exception as e:
        job.error = f"report failed to process with: {e}"
        logging.error(job.error)
        logging.exception(e)
    job.save()
    return job_id


@shared_task
def job_completed_with_error(job_id):
    job = Job.objects.get(pk=job_id)
    job.state = models.JobState.COMPLETED
    job.save()
