

import io
from unittest.mock import MagicMock, patch, call
import pytest
from stixify.worker.tasks import job_completed_with_error, new_task, process_post
from stixify.web import models
from dogesec_commons.stixifier.stixifier import StixifyProcessor

from stixify.worker import tasks

@pytest.fixture(autouse=True, scope="module")
def celery_eager():
    from stixify.worker.celery import app

    app.conf.task_always_eager = True
    app.conf.broker_url = None
    yield
    app.conf.task_always_eager = False


@pytest.mark.django_db
def test_new_task(stixify_job):
    with (
        patch("stixify.worker.tasks.process_post.run") as mock_process_post,
        patch("stixify.worker.tasks.job_completed_with_error.run") as mock_job_completed_with_error,
    ):
        new_task(stixify_job)
        mock_process_post.assert_called_once_with(stixify_job.id)
        mock_job_completed_with_error.assert_called_once_with(stixify_job.id)


@pytest.mark.django_db
def test_process_post_job__fails(stixify_job):
    with (
        patch("stixify.worker.tasks.StixifyProcessor", side_effect=ValueError) as mock_stixify_processor_cls,
    ):
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        assert stixify_job.error == "failed to process report"

@pytest.fixture
def fake_stixifier_processor():
    mocked_processor = MagicMock()
    mocked_processor.summary = "Summarized post"
    mocked_processor.md_file.open.return_value = io.BytesIO(b"Generated MD File")
    mocked_processor.incident = None
    mocked_processor.txt2stix_data.model_dump.return_value = {"data": "data is here"}
    return mocked_processor
    
@pytest.mark.django_db
def test_process_post_job(stixify_job, fake_stixifier_processor):
    file = stixify_job.file

    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.pdf_converter.make_conversion") as mock_convert_pdf,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        file.refresh_from_db()
        mock_convert_pdf.assert_called_once()
        mock_stixify_processor_cls.assert_called_once()
        mock_stixify_processor_cls.return_value.setup.assert_called_once()
        assert mock_stixify_processor_cls.return_value.setup.call_args[1]['extra'] == dict(_stixify_file_id=str(file.id))
        assert file.summary == fake_stixifier_processor.summary
        assert file.txt2stix_data == {"data": "data is here"}
        assert file.markdown_file.read() == b"Generated MD File"
        process_stream: io.BytesIO = mock_stixify_processor_cls.call_args[0][0]
        process_stream.seek(0)
        assert process_stream.read() == file.file.read()
        mock_stixify_processor_cls.assert_called_once_with(
            process_stream,
            stixify_job.profile,
            job_id=stixify_job.id,
            file2txt_mode=file.mode,
            report_id=file.id,
            always_extract=True
        )

@pytest.mark.django_db
def test_process_post_with_incident(stixify_job, fake_stixifier_processor):
    incident = fake_stixifier_processor.incident = MagicMock()
    incident.describes_incident = True
    incident.explanation = "some explanation"
    incident.incident_classification = []

    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()
        file = models.File.objects.get(pk=stixify_job.file_id)
        assert file.ai_describes_incident == incident.describes_incident
        assert file.ai_incident_summary == incident.explanation
        assert file.ai_incident_classification == incident.incident_classification

@pytest.mark.django_db
def test_process_post_full(stixify_job):
    process_post.si(stixify_job.id).delay()
    file = models.File.objects.get(pk=stixify_job.file_id)
    stixify_job.refresh_from_db()
    assert stixify_job.error == None, stixify_job.error
    assert tuple(file.archived_pdf.read(4)) == (0x25,0x50,0x44,0x46)
