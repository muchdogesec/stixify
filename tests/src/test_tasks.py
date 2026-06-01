import io
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import uuid
import pytest
from stixify.worker.tasks import job_completed_with_error, new_task, process_post
from stixify.web import models
from dogesec_commons.stixifier.stixifier import StixifyProcessor
from dogesec_commons.stixifier.models import Profile
from django.core.files.base import ContentFile
from txt2stix.txt2stix import Txt2StixData

from stixify.worker import tasks


@pytest.fixture(autouse=True)
def always_eager(celery_eager):
    yield


@pytest.mark.django_db
def test_new_task(stixify_job):
    with (
        patch("stixify.worker.tasks.process_post.run") as mock_process_post,
        patch(
            "stixify.worker.tasks.job_completed_with_error.run"
        ) as mock_job_completed_with_error,
    ):
        new_task(stixify_job)
        mock_process_post.assert_called_once_with(stixify_job.id)
        mock_job_completed_with_error.assert_called_once_with(stixify_job.id)


@pytest.mark.django_db
def test_process_post_job__fails(stixify_job):
    with (
        patch(
            "stixify.worker.tasks.StixifyProcessor", side_effect=ValueError
        ) as mock_stixify_processor_cls,
    ):
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        assert stixify_job.error == "failed to process report"

        mock_stixify_processor_cls.side_effect = ValueError("some error")
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        assert stixify_job.error == "failed to process report: some error"


@pytest.fixture
def fake_stixifier_processor(tmpdir):
    mocked_processor = MagicMock()
    mocked_processor.summary = "Summarized post"
    mocked_processor.md_file.open.return_value = io.BytesIO(b"Generated MD File")
    mocked_processor.incident = None
    mocked_processor.txt2stix_data = Txt2StixData.model_validate(fake_txt2stix_data())
    mocked_processor.md_images = []
    mocked_processor.tmpdir = MagicMock()
    mocked_processor.filename = "test.md"
    return mocked_processor


@pytest.fixture
def stixify_reprocess_job(stixify_job):
    stixify_job.type = models.JobType.REPROCESS_POSTS
    stixify_job.extra = {}
    stixify_job.save(update_fields=["type", "extra"])
    stixify_job.file.set_txt2stix_data(fake_txt2stix_data())
    return stixify_job


@pytest.mark.django_db
def test_process_post_job(stixify_job, fake_stixifier_processor):
    file = stixify_job.file

    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.pdf_converter.make_conversion") as mock_convert_pdf,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        file.refresh_from_db()
        mock_convert_pdf.assert_called_once()
        mock_stixify_processor_cls.assert_called_once()
        mock_stixify_processor_cls.return_value.setup.assert_called_once()
        assert mock_stixify_processor_cls.return_value.setup.call_args[1][
            "extra"
        ] == dict(_stixify_file_id=str(file.id))
        assert file.txt2stix_data["content_check"]["threat_score"] == 8
        assert file.ai_describes_incident == True
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
        )
        mock_create_embedding.assert_called_once_with(include_non_incident=False)


@pytest.mark.django_db
def test_process_post_mhtml_pdf_mode(stixify_job, fake_stixifier_processor):
    stixify_job.refresh_from_db()
    file = stixify_job.file
    file.mode = "mhtml-pdf"
    file.pdf_file = ContentFile(b"PDF content", name="test.pdf")
    file.save()
    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.pdf_converter.convert_mhtml_to_pdf") as mock_convert_pdf,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()
        process_stream: io.BytesIO = mock_stixify_processor_cls.call_args[0][0]
        process_stream.seek(0)
        mock_stixify_processor_cls.assert_called_once_with(
            process_stream,
            stixify_job.profile,
            job_id=stixify_job.id,
            file2txt_mode="pdf",
            report_id=file.id,
        )
        assert process_stream.read() == b"PDF content"


@pytest.mark.django_db
def test_process_post_reprocess_skip_extraction_no_existing_data(
    stixify_reprocess_job, fake_stixifier_processor
):
    file = stixify_reprocess_job.file
    stixify_reprocess_job.extra = {"skip_extraction": True}
    stixify_reprocess_job.save(update_fields=["extra"])
    file.markdown_file.save("test.md", io.BytesIO(b"test content"))
    file.txt2stix_data = None
    file.save(update_fields=["markdown_file", "txt2stix_data"])

    with patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls:
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        new_task(stixify_reprocess_job)
        stixify_reprocess_job.refresh_from_db()
        assert "no existing extraction data" in stixify_reprocess_job.error
        assert stixify_reprocess_job.state == models.JobState.FAILED
        assert (
            stixify_reprocess_job.file.markdown_file.read() == b"test content"
        ), "File should not be removed if reprocess fails"


def fake_txt2stix_data():
    return Txt2StixData.model_validate(
        dict(
            content_check=dict(
                threat_score=8,
                describes_incident=True,
                explanation="some explanation",
                incident_classification=["class1", "class2"],
                summary="some summary",
            )
        )
    )


@pytest.mark.django_db
def test_process_post_reprocess_skip_extraction_uses_existing_data(
    stixify_reprocess_job, fake_stixifier_processor
):
    file = stixify_reprocess_job.file
    file.markdown_file.save("test.md", io.BytesIO(b"test content"))
    file.save(update_fields=["markdown_file", "txt2stix_data"])
    stixify_reprocess_job.extra = {"skip_extraction": True}
    stixify_reprocess_job.save(update_fields=["extra"])

    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.pdf_converter.make_conversion") as mock_convert_pdf,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        new_task(stixify_reprocess_job)
        fake_stixifier_processor.process.assert_not_called()
        fake_stixifier_processor.txt2stix.assert_called_once()
        fake_stixifier_processor.write_bundle.assert_called_once()
        fake_stixifier_processor.upload_to_arango.assert_called_once()
        mock_convert_pdf.assert_not_called()
        mock_create_embedding.assert_called_once()


@pytest.mark.django_db
def test_process_post_reprocess_with_profile_switch(
    stixify_reprocess_job, fake_stixifier_processor, stixifier_profile
):
    new_profile = Profile.objects.create(
        name="new-test-profile",
        extractions=stixifier_profile.extractions,
        extract_text_from_image=stixifier_profile.extract_text_from_image,
        defang=stixifier_profile.defang,
        relationship_mode=stixifier_profile.relationship_mode,
        ai_settings_relationships=stixifier_profile.ai_settings_relationships,
        ai_settings_extractions=stixifier_profile.ai_settings_extractions,
        ai_content_check_provider=stixifier_profile.ai_content_check_provider,
        ai_create_attack_flow=stixifier_profile.ai_create_attack_flow,
    )
    stixify_reprocess_job.extra = {
        "skip_extraction": False,
        "profile_id": str(new_profile.pk),
    }
    stixify_reprocess_job.save(update_fields=["extra"])

    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_reprocess_job.id).delay()
        stixify_reprocess_job.file.refresh_from_db()
        fake_stixifier_processor.process.assert_called_once()
        assert str(stixify_reprocess_job.file.profile_id) == str(new_profile.pk)
        mock_create_embedding.assert_called_once()


@pytest.mark.django_db
def test_process_post_with_incident(stixify_job, fake_stixifier_processor, tmpdir):
    fake_stixifier_processor.txt2stix_data.content_check.describes_incident = True
    fake_stixifier_processor.tmpdir = Path(tmpdir)


    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
        patch("stixify.worker.pdf_converter.make_conversion") as mock_convert_pdf,

    ):
        mock_convert_pdf.side_effect = lambda input_path, output_path: output_path.write_bytes(b"PDF content")
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        new_task(stixify_job)
        mock_create_embedding.assert_called_once_with(include_non_incident=False)
        mock_convert_pdf.assert_called_once_with("test.md", fake_stixifier_processor.tmpdir/"converted_pdf.pdf")
        file = models.File.objects.get(pk=stixify_job.file_id)
        assert file.ai_describes_incident is True
        assert file.ai_incident_summary == "some explanation"
        assert file.ai_incident_classification == ["class1", "class2"]


@pytest.mark.parametrize(
    "settings_value",
    [
        True,
        False,
    ],
)
@pytest.mark.django_db
def test_process_post__creates_embedding(
    stixify_job, fake_stixifier_processor, settings_value, settings
):
    settings.CREATE_EMBEDDING_INCLUDE_NON_INCIDENT = settings_value
    with (
        patch("stixify.worker.tasks.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
        patch("stixify.worker.pdf_converter.make_conversion") as mock_convert_pdf,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()

        mock_create_embedding.assert_called_once_with(
            include_non_incident=settings_value
        )


@pytest.mark.django_db
def test_process_post_full(stixify_job):
    process_post.si(stixify_job.id).delay()
    file = models.File.objects.get(pk=stixify_job.file_id)
    stixify_job.refresh_from_db()
    assert stixify_job.error == None, stixify_job.error
    assert tuple(file.archived_pdf.read(4)) == (0x25, 0x50, 0x44, 0x46)


@pytest.mark.django_db
def test_job_completed_with_error__failed(stixify_job):
    stixify_job.error = "failed"
    stixify_job.save()
    file_id = stixify_job.file.pk
    job_completed_with_error(stixify_job.id)
    stixify_job.refresh_from_db()
    assert stixify_job.file == None
    assert stixify_job.state == models.JobState.FAILED
    with pytest.raises(models.File.DoesNotExist):
        models.File.objects.get(pk=file_id)
    assert stixify_job.completion_time != None


@pytest.mark.django_db
def test_job_completed_with_error__success(stixify_job):
    file_id = uuid.UUID(stixify_job.file.pk)
    job_completed_with_error(stixify_job.id)
    stixify_job.refresh_from_db()
    assert stixify_job.file.pk == file_id
    assert stixify_job.state == models.JobState.COMPLETED
    assert stixify_job.completion_time != None
