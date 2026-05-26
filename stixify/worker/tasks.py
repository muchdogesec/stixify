from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import uuid
from stixify.web.models import Job, File
from stixify.web import models
from celery import shared_task
from dogesec_commons.stixifier.stixifier import StixifyProcessor, ReportProperties

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.core.files.base import File as DjangoFile
from django.core.files.base import File as DjangoFile
from django.db import transaction
import stix2

from stixify.worker import helpers, pdf_converter
from django.conf import settings
from txt2stix.txt2stix import Txt2StixData


POLL_INTERVAL = 1


def new_task(job: Job):
    (process_post.s(job.id) | job_completed_with_error.si(job.id)).apply_async(
        countdown=POLL_INTERVAL, root_id=str(job.id), task_id=str(job.id)
    )

def create_reprocessing_job(file: File, options: dict = None):
    options = options or {}
    job  = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.REPROCESS_POSTS,
        file=file,
        state=models.JobState.PENDING,
        extra=options,
    )
    new_task(job)
    return job

@shared_task
def process_post(job_id, *args):
    job = Job.objects.get(id=job_id)
    file = job.file
    try:
        job.state = models.JobState.PROCESSING
        job.save()
        processor = StixifyProcessor(
            file.process_file,
            job.profile,
            job_id=job.id,
            file2txt_mode=file.process_mode,
            report_id=file.id,
        )
        external_refs = [
            dict(
                source_name="stixify_profile_id",
                external_id=str(job.profile.id),
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
            kwargs=dict(external_references=external_refs),
        )
        processor.setup(
            report_prop=report_props, extra=dict(_stixify_file_id=str(file.id))
        )
        skip_extraction = bool((job.extra or {}).get("skip_extraction"))

        # remove existing values for this file that are not in the new upload (handles deletions and modifications)
        models.ObjectValue.objects.filter(file_id=file.id).delete()
        if job.type == models.JobType.REPROCESS_POSTS and skip_extraction:
            processor.output_md = file.markdown_file.open().read().decode()
            txt2stix_data = None
            if not file.txt2stix_data:
                raise Exception("no existing extraction data to use for reprocess with skip_extraction=true")
            txt2stix_data = Txt2StixData.model_validate(file.txt2stix_data)
            processor.txt2stix(txt2stix_data)
            processor.write_bundle(processor.bundler)
            processor.upload_to_arango()
        else:
            processor.process()
        
        with transaction.atomic(): # revert to old file if something goes wrong during processing
            new_profile_id = (job.extra or {}).get("profile_id")
            if new_profile_id:
                file.profile_id = new_profile_id
                file.save(update_fields=["profile"])
            file.set_txt2stix_data(processor.txt2stix_data)
            file.create_embedding(include_non_incident=settings.CREATE_EMBEDDING_INCLUDE_NON_INCIDENT)

            if job.type == models.JobType.IMPORT_FILE: # only update files for import jobs, reprocess jobs should keep the same file references
                file.markdown_file.save("markdown.md", processor.md_file.open(), save=True)
                models.FileImage.objects.filter(report=file).delete()  # remove old references

                for image in processor.md_images:
                    models.FileImage.objects.create(
                        report=file, file=DjangoFile(image, image.name), name=image.name
                    )

                converted_file_path = processor.tmpdir / "converted_pdf.pdf"
                pdf_converter.make_conversion(processor.filename, converted_file_path)
                file.pdf_file.save(
                    converted_file_path.name, open(converted_file_path, mode="rb")
                )
                file.save(update_fields=['markdown_file', 'pdf_file'])
    except Exception as e:
        error = str(e)
        job.error = "failed to process report"
        if error:
            job.error += f": {error}"
        logging.error(job.error)
        logging.exception(e)
    job.save()
    return job_id


@shared_task
def job_completed_with_error(job_id):
    job = Job.objects.get(pk=job_id)
    state = models.JobState.COMPLETED
    if job.error:
        state = models.JobState.FAILED
        if job.type == models.JobType.IMPORT_FILE:
            job.file and job.file.delete()
    Job.objects.filter(pk=job_id).update(state=state, completion_time=datetime.now(UTC))

@shared_task
def update_knowledgebase(job_id):
    job = models.Job.objects.get(pk=job_id)
    try:
        helpers.run_on_collections(job, job.extra["knowledgebase"])
    except Exception as e:
        job.error = str(e)
    job.save(update_fields=["error"])
