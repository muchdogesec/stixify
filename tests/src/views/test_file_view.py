from stixify.web import models
from stixify.web.serializers import FileSerializer, JobSerializer
from stixify.web.views import FileView
import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
import io
from stixify.web.md_helper import MarkdownImageReplacer
from tests.utils import Transport


@pytest.mark.django_db
def test_create(client, stixifier_profile, api_schema):
    payload = dict(
        file=SimpleUploadedFile(name="name.pdf", content=b"file content"),
        profile_id=stixifier_profile.id,
        mode="md",
        name="Upload test",
        report_id="report--567681d6-2817-4d84-84fb-87b2f059b92e",
    )
    with (
        patch(
            "stixify.web.views.JobSerializer", side_effect=JobSerializer
        ) as mock_job_serializer_cls,
        patch("stixify.web.views.new_task") as mock_new_task,
    ):
        resp = client.post("/api/v1/files/", data=payload)
        assert resp.status_code == 201, resp.content
        job = models.Job.objects.get(pk=resp.data["id"])
        file = models.File.objects.get(pk="567681d6-2817-4d84-84fb-87b2f059b92e")
        mock_job_serializer_cls.assert_called_once_with(job, **mock_job_serializer_cls.call_args[1])
        mock_new_task.assert_called_once_with(job)
        assert resp.data["file"]["id"] == "567681d6-2817-4d84-84fb-87b2f059b92e"
        assert file.file.read() == b"file content"
        resp.wsgi_request.FILES.clear()
        api_schema['/api/v1/files/']['POST'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_file_extractions(client, stixify_file, api_schema):
    post = models.File.objects.get(pk="dcbeb240-8dd6-4892-8e9e-7b6bda30e454")
    post.txt2stix_data = {"data": "here"}
    post.save()
    resp = client.get(
        "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/extractions/",
        data=None,
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data == post.txt2stix_data
    api_schema['/api/v1/files/{file_id}/extractions/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_file_extractions_no_data(client, stixify_file, api_schema):
    post = models.File.objects.get(pk="dcbeb240-8dd6-4892-8e9e-7b6bda30e454")

    resp = client.get(
        "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/extractions/",
        data=None,
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data == {}
    api_schema['/api/v1/files/{file_id}/extractions/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_file_markdown(client, stixify_file, api_schema):
    post_file = models.File.objects.get(pk="dcbeb240-8dd6-4892-8e9e-7b6bda30e454")
    post_file.markdown_file.save("markdown.md", io.StringIO("My markdown"))
    images = [
        models.FileImage.objects.create(
            report=post_file, file=SimpleUploadedFile("nb", b"f1"), name="image1"
        ),
        models.FileImage.objects.create(
            report=post_file, file=SimpleUploadedFile("na", b"f2"), name="image2"
        ),
    ]
    with (
        patch.object(
            MarkdownImageReplacer, "get_markdown", return_value="Built Markdown"
        ) as mock_get_markdown,
    ):
        resp = client.get(
            "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/markdown/",
            data=None,
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.content
        assert resp.headers["content-type"] == "text/markdown"
        assert resp.getvalue() == b"Built Markdown"
        mock_get_markdown.assert_called_once_with(
            "http://testserver/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/markdown/",
            "My markdown",
            {im.name: im.file.url for im in images},
        )
        api_schema['/api/v1/files/{file_id}/markdown/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_file_images(client, stixify_file, api_schema):
    post = models.File.objects.get(pk="dcbeb240-8dd6-4892-8e9e-7b6bda30e454")
    models.FileImage.objects.create(
        report=post, file=SimpleUploadedFile("nb", b"f1"), name="image1"
    )
    models.FileImage.objects.create(
        report=post, file=SimpleUploadedFile("na", b"f2"), name="image2"
    )

    resp = client.get(
        "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/images/",
    )
    assert resp.status_code == 200, resp.content
    assert "images" in resp.data
    assert len(resp.data["images"]) == 2
    api_schema['/api/v1/files/{file_id}/images/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_file_images_no_images(client, stixify_file, api_schema):
    post = models.File.objects.get(pk="dcbeb240-8dd6-4892-8e9e-7b6bda30e454")

    resp = client.get(
        "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/images/",
    )
    assert resp.status_code == 200, resp.content
    assert "images" in resp.data
    assert len(resp.data["images"]) == 0
    api_schema['/api/v1/files/{file_id}/images/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_retrieve_file(client, stixify_file, api_schema):
    resp = client.get(
        "/api/v1/files/dcbeb240-8dd6-4892-8e9e-7b6bda30e454/",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data["id"] == "dcbeb240-8dd6-4892-8e9e-7b6bda30e454"

    resp = client.get(
        "/api/v1/files/abcdb240-8dd6-4892-8e9e-7b6bda30e454/",
    )
    assert resp.status_code == 404, resp.content
    api_schema['/api/v1/files/{file_id}/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.django_db
def test_list_files(client, stixify_file, more_files, api_schema):
    resp = client.get(
        "/api/v1/files/",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data["total_results_count"] == 4
    assert len(resp.data["files"]) == 4
    api_schema['/api/v1/files/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.fixture
def more_files(stixifier_profile):
    return [
        models.File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("file1.txt", b"File Content 1", "text/markdown"),
            profile=stixifier_profile,
            mode="md",
            ai_describes_incident=True,
            name="First file, special",
        ),
        models.File.objects.create(
            id="aadbe23d-192c-488d-8ce9-96aa2613453f",
            file=SimpleUploadedFile("file2.txt", b"File Content 2", "text/markdown"),
            profile=stixifier_profile,
            mode="txt",
            ai_incident_classification=["other", "apt_group", "data_leak"],
            name="second file, not breakable",
        ),
        models.File.objects.create(
            id="bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
            file=SimpleUploadedFile(
                "portable.pdf", b"File Portable 3", "application/pdf"
            ),
            profile=stixifier_profile,
            ai_describes_incident=False,
            mode="pdf",
            ai_incident_classification=["data_leak", "vulnerability"],
            name="Forth file, special, breakable",
        ),
    ]


@pytest.mark.parametrize(
    "filters,expected_ids",
    [
        (
            None,
            [
                "f3848d80-b14d-4aa6-b3a6-94bce54b217e",
                "aadbe23d-192c-488d-8ce9-96aa2613453f",
                "bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
                "dcbeb240-8dd6-4892-8e9e-7b6bda30e454",
            ],
        ),
        (
            dict(name="special"),
            [
                "f3848d80-b14d-4aa6-b3a6-94bce54b217e",
                "bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
                "dcbeb240-8dd6-4892-8e9e-7b6bda30e454",
            ],
        ),
        (
            dict(name="kable"),
            [
                "aadbe23d-192c-488d-8ce9-96aa2613453f",
                "bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
            ],
        ),
        (
            dict(ai_describes_incident="false"),
            [
                "bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
            ],
        ),
        (
            dict(ai_describes_incident="true"),
            [
                "f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            ],
        ),
        (
            dict(
                ai_incident_classification=["ransomware", "cyber_crime"],
            ),
            [],
        ),
        (
            dict(ai_incident_classification=["apt_group"]),
            [
                "aadbe23d-192c-488d-8ce9-96aa2613453f",
            ],
        ),
        (
            dict(ai_incident_classification=["data_leak", "cyber_crime"]),
            [
                "aadbe23d-192c-488d-8ce9-96aa2613453f",
                "bd5c8992-e1f2-42ef-8ad2-8003bc4fcedb",
            ],
        ),
    ],
)
@pytest.mark.django_db
def test_list_posts_filter(client, stixify_file, more_files, filters, expected_ids, api_schema):
    resp = client.get("/api/v1/files/", query_params=filters)
    assert resp.status_code == 200, resp.content
    assert {post["id"] for post in resp.data["files"]} == set(expected_ids)
    assert resp.data["total_results_count"] == len(expected_ids)
    api_schema['/api/v1/files/']['GET'].validate_response(Transport.get_st_response(resp))

