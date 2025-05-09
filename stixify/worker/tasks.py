import logging
import os
from pathlib import Path
from stixify.web.models import Job, File
from stixify.web import models
from celery import shared_task
from dogesec_commons.stixifier.stixifier import StixifyProcessor, ReportProperties
from dogesec_commons.stixifier.summarizer import parse_summarizer_model

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.core.files.base import File as DjangoFile
from django.core.files.base import File as DjangoFile
import stix2
POLL_INTERVAL = 1


def new_task(job: Job, file: File):
    ( process_post.s(file.file.name, job.id) | job_completed_with_error.si(job.id)).apply_async(
        countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id)
    )

@shared_task
def process_post(filename, job_id, *args):
    job = Job.objects.get(id=job_id)
    try:
        job.state = models.JobState.PROCESSING
        job.save()
        processor = StixifyProcessor(default_storage.open(filename), job.profile, job_id=job.id, file2txt_mode=job.file.mode, report_id=job.file.id, always_extract=True)
        report_props = ReportProperties(
            name=job.file.name,
            identity=stix2.Identity(**job.file.identity),
            tlp_level=job.file.tlp_level,
            confidence=job.file.confidence,
            labels=job.file.labels,
            created=job.file.created,
            kwargs=dict(external_references=[
                dict(source_name='stixify_profile_id', external_id=str(job.profile.id)),
            ])
        )
        processor.setup(report_prop=report_props, extra=dict(_stixify_file_id=str(job.file.id)))
        processor.process()
        if processor.incident:
            job.file.ai_describes_incident = processor.incident.describes_incident
            job.file.ai_incident_summary = processor.incident.explanation
            job.file.ai_incident_classification = processor.incident.incident_classification

        job.file.txt2stix_data = processor.txt2stix_data.model_dump(mode="json", exclude_defaults=True, exclude_unset=True, exclude_none=True)
        job.file.summary = processor.summary
        job.file.markdown_file.save('markdown.md', processor.md_file.open(), save=True)
        
        models.FileImage.objects.filter(report=job.file).delete() # remove old references

        for image in processor.md_images:
            models.FileImage.objects.create(report=job.file, file=DjangoFile(image, image.name), name=image.name)
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
    if job.error:
        job.state = models.JobState.FAILED
    job.save()
