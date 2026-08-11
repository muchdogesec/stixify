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
from django.test import override_settings
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
def test_new_task_detached_reprocesses_each_file(stixify_file):
    file_ids = [str(stixify_file.id), str(stixify_file.id)]
    job = models.Job.objects.create(
        type=models.JobType.REPROCESS_FILES,
        extra={
            "file_ids": file_ids,
            "progress": {
                "total_items": 2,
                "processed_items": 0,
                "failed_processes": 0,
                "unprocessed_items": 2,
                "current_file_id": None,
                "current_index": None,
                "stopped_early": False,
                "stop_reason": None,
                "errors": [],
            },
        },
    )
    with (
        patch("stixify.worker.tasks.process_post.run") as mock_process_file,
        patch(
            "stixify.worker.tasks.job_completed_with_error.run"
        ) as mock_completed,
    ):
        new_task(job)

    assert mock_process_file.call_args_list == [
        call(job.id, file_ids[0]),
        call(job.id, file_ids[1]),
    ]
    mock_completed.assert_called_once_with(job.id)


@pytest.mark.django_db
def test_process_post_job__fails(stixify_job):
    with (
        patch(
            "stixify.worker.process_post.StixifyProcessor", side_effect=ValueError
        ) as mock_stixify_processor_cls,
    ):
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        assert stixify_job.error == "failed to process file"

        mock_stixify_processor_cls.side_effect = ValueError("some error")
        process_post.si(stixify_job.id).delay()
        stixify_job.refresh_from_db()
        assert stixify_job.error == "failed to process file: some error"


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
    stixify_job.type = models.JobType.REPROCESS_FILES
    stixify_job.extra = {}
    stixify_job.save(update_fields=["type", "extra"])
    stixify_job.file.set_txt2stix_data(fake_txt2stix_data())
    return stixify_job


@pytest.mark.django_db
def test_process_post_job(stixify_job, fake_stixifier_processor):
    file = stixify_job.file

    with (
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.process_post.pdf_converter.make_conversion") as mock_convert_pdf,
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
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.process_post.pdf_converter.convert_mhtml_to_pdf") as mock_convert_pdf,
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

    with patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls:
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
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch("stixify.worker.process_post.pdf_converter.make_conversion") as mock_convert_pdf,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        new_task(stixify_reprocess_job)
        fake_stixifier_processor.file2txt.assert_not_called()
        fake_stixifier_processor.txt2stix.assert_called_once()
        fake_stixifier_processor.write_bundle.assert_called_once()
        fake_stixifier_processor.upload_to_arango.assert_called_once()
        mock_convert_pdf.assert_not_called()
        mock_create_embedding.assert_called_once()



@pytest.mark.django_db
def test_process_post_reprocess_skip_extraction_acquires_lock(
    stixify_reprocess_job, fake_stixifier_processor
):
    from django.core.cache import cache
    from stixify.worker.process_post import ARANGO_UPLOAD_COUNTER_KEY

    file = stixify_reprocess_job.file
    file.markdown_file.save("test.md", io.BytesIO(b"test content"))
    file.save(update_fields=["markdown_file", "txt2stix_data"])
    stixify_reprocess_job.extra = {"skip_extraction": True}
    stixify_reprocess_job.save(update_fields=["extra"])

    cache.clear()

    with (
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_reprocess_job.id).delay()

        lock_key = f"arango_upload_lock:{stixify_reprocess_job.id}"
        assert cache.get(lock_key) is None, "Lock should be released after upload"
        assert cache.get(ARANGO_UPLOAD_COUNTER_KEY, 0) == 0, "Counter should be 0 after upload"
        fake_stixifier_processor.upload_to_arango.assert_called_once()


@pytest.mark.django_db
def test_process_post_concurrent_uploads_limited(
    stixify_reprocess_job, fake_stixifier_processor
):
    from django.core.cache import cache
    from stixify.worker.process_post import ARANGO_UPLOAD_COUNTER_KEY, MAX_CONCURRENT_UPLOADS

    file = stixify_reprocess_job.file
    file.markdown_file.save("test.md", io.BytesIO(b"test content"))
    file.save(update_fields=["markdown_file", "txt2stix_data"])

    cache.clear()

    with (
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor

        cache.set(ARANGO_UPLOAD_COUNTER_KEY, MAX_CONCURRENT_UPLOADS, 300)

        from stixify.worker.process_post import acquire_upload_lock
        with pytest.raises(TimeoutError):
            acquire_upload_lock(stixify_reprocess_job.id, wait_timeout=0.1)
        cache.clear()



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
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_reprocess_job.id).delay()
        stixify_reprocess_job.file.refresh_from_db()
        fake_stixifier_processor.file2txt.assert_called_once()
        fake_stixifier_processor.txt2stix.assert_called_once()
        assert str(stixify_reprocess_job.file.profile_id) == str(new_profile.pk)
        assert mock_stixify_processor_cls.call_args.args[1] == new_profile
        mock_create_embedding.assert_called_once()


@pytest.mark.django_db
def test_process_post_with_incident(stixify_job, fake_stixifier_processor, tmpdir):
    fake_stixifier_processor.txt2stix_data.content_check.describes_incident = True
    fake_stixifier_processor.tmpdir = Path(tmpdir)


    with (
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
        patch("stixify.worker.process_post.pdf_converter.make_conversion") as mock_convert_pdf,

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
        patch("stixify.worker.process_post.StixifyProcessor") as mock_stixify_processor_cls,
        patch.object(models.File, "create_embedding") as mock_create_embedding,
        patch("stixify.worker.process_post.pdf_converter.make_conversion") as mock_convert_pdf,
    ):
        mock_stixify_processor_cls.return_value = fake_stixifier_processor
        process_post.si(stixify_job.id).delay()

        mock_create_embedding.assert_called_once_with(
            include_non_incident=settings_value
        )


@pytest.mark.django_db
def test_process_post_full(stixify_job):
    with patch("stixify.worker.process_post.pdf_converter.make_conversion") as mock_convert_pdf:
        mock_convert_pdf.side_effect = lambda input_path, output_path: output_path.write_bytes(b"%PDF-1.4")
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


def detached_reprocess_job(file_ids, **options):
    progress = {
        "total_items": len(file_ids),
        "processed_items": 0,
        "failed_processes": 0,
        "unprocessed_items": len(file_ids),
        "current_file_id": None,
        "current_index": None,
        "stopped_early": False,
        "stop_reason": None,
        "errors": [],
    }
    return models.Job.objects.create(
        type=models.JobType.REPROCESS_FILES,
        extra={"file_ids": file_ids, "progress": progress, **options},
    )


@pytest.mark.django_db
def test_detached_reprocess_updates_progress(
    stixify_file, fake_stixifier_processor
):
    job = detached_reprocess_job([str(stixify_file.id)], skip_extraction=False)
    with (
        patch("stixify.worker.process_post.StixifyProcessor") as processor_class,
        patch.object(models.File, "create_embedding"),
    ):
        processor_class.return_value = fake_stixifier_processor
        process_post(job.id, stixify_file.id)

    job.refresh_from_db()
    assert job.extra["progress"] == {
        "total_items": 1,
        "processed_items": 1,
        "failed_processes": 0,
        "unprocessed_items": 0,
        "current_file_id": str(stixify_file.id),
        "current_index": 0,
        "stopped_early": False,
        "stop_reason": None,
        "errors": [],
    }


@pytest.mark.django_db
@override_settings(REPROCESS_MAX_FAILED_PROCESSES=10)
def test_detached_reprocess_stops_after_ten_failures(stixify_file):
    file_ids = [str(stixify_file.id)] * 11
    job = detached_reprocess_job(file_ids, skip_extraction=False)

    with patch(
        "stixify.worker.process_post.StixifyProcessor", side_effect=ValueError("bad file")
    ) as processor_class:
        for file_id in file_ids:
            process_post(job.id, file_id)

    job.refresh_from_db()
    progress = job.extra["progress"]
    assert processor_class.call_count == 10
    assert progress["processed_items"] == 0
    assert progress["failed_processes"] == 10
    assert progress["unprocessed_items"] == 1
    assert progress["stopped_early"] is True
    assert progress["stop_reason"] == "failure_limit_reached"
    assert len(progress["errors"]) == 10
    assert set(progress["errors"][0]) == {"file_id", "message"}

    job_completed_with_error(job.id)
    job.refresh_from_db()
    assert job.state == models.JobState.FAILED
    assert job.error == "failed to reprocess 10 file(s)"
    assert job.extra["progress"]["current_file_id"] is None


@pytest.mark.django_db
def test_detached_reprocess_is_failed_when_one_file_fails(
    stixify_file, fake_stixifier_processor
):
    file_ids = [str(stixify_file.id), str(stixify_file.id)]
    job = detached_reprocess_job(file_ids, skip_extraction=False)

    with (
        patch(
            "stixify.worker.process_post.StixifyProcessor",
            side_effect=[ValueError("bad file"), fake_stixifier_processor],
        ),
        patch.object(models.File, "create_embedding"),
    ):
        for file_id in file_ids:
            process_post(job.id, file_id)
    job_completed_with_error(job.id)

    job.refresh_from_db()
    assert job.state == models.JobState.FAILED
    assert job.extra["progress"]["processed_items"] == 1
    assert job.extra["progress"]["failed_processes"] == 1
    assert job.extra["progress"]["unprocessed_items"] == 0


@pytest.mark.django_db
def test_reprocess_restores_object_values_after_failure(
    stixify_file, fake_stixifier_processor
):
    original = models.ObjectValue.objects.create(
        file=stixify_file,
        stix_id="indicator--11111111-1111-4111-8111-111111111111",
        type="indicator",
        values={"name": "original"},
    )
    job = detached_reprocess_job([str(stixify_file.id)], skip_extraction=False)
    fake_stixifier_processor.upload_to_arango.side_effect = RuntimeError("upload failed")

    with (
        patch("stixify.worker.process_post.StixifyProcessor") as processor_class,
        patch.object(models.File, "create_embedding"),
    ):
        processor_class.return_value = fake_stixifier_processor
        process_post(job.id, stixify_file.id)

    restored = models.ObjectValue.objects.get(
        file=stixify_file, stix_id=original.stix_id
    )
    assert restored.values == {"name": "original"}
