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

from stixify.worker import pdf_converter
POLL_INTERVAL = 1


def new_task(job: Job):
    ( process_post.s(job.id) | job_completed_with_error.si(job.id)).apply_async(
        countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id)
    )

@shared_task
def process_post(job_id, *args):
    job = Job.objects.get(id=job_id)
    file = job.file
    try:
        job.state = models.JobState.PROCESSING
        job.save()
        processor = StixifyProcessor(default_storage.open(file.file.name), job.profile, job_id=job.id, file2txt_mode=file.mode, report_id=file.id, always_extract=True)
        report_props = ReportProperties(
            name=file.name,
            identity=stix2.Identity(**file.identity),
            tlp_level=file.tlp_level,
            confidence=file.confidence,
            labels=file.labels,
            created=file.created,
            kwargs=dict(external_references=[
                dict(source_name='stixify_profile_id', external_id=str(job.profile.id)),
            ])
        )
        processor.setup(report_prop=report_props, extra=dict(_stixify_file_id=str(file.id)))
        processor.process()
        if processor.incident:
            file.ai_describes_incident = processor.incident.describes_incident
            file.ai_incident_summary = processor.incident.explanation
            file.ai_incident_classification = processor.incident.incident_classification

        file.txt2stix_data = processor.txt2stix_data.model_dump(mode="json", exclude_defaults=True, exclude_unset=True, exclude_none=True)
        file.summary = processor.summary
        file.markdown_file.save('markdown.md', processor.md_file.open(), save=True)
        
        models.FileImage.objects.filter(report=file).delete() # remove old references

        for image in processor.md_images:
            models.FileImage.objects.create(report=file, file=DjangoFile(image, image.name), name=image.name)

        converted_file_path = processor.tmpdir/'converted_pdf.pdf'
        pdf_converter.make_conversion(processor.filename, converted_file_path)
        file.pdf_file.save(converted_file_path.name, open(converted_file_path, mode='rb'))

        file.save()
    except Exception as e:
        job.error = "failed to process report"
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
