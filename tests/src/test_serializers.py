import pytest
from django.core.files.base import ContentFile
from stixify.web.serializers import (
    FilePatchSerializer,
    FileSerializer,
    ReprocessFilesSerializer,
)


@pytest.mark.django_db
class TestFilePatchSerializerLabels:
    def test_patch_with_valid_labels(self, stixify_file):
        data = {"labels": ["malware,apt-28,c2"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert set(stixify_file.labels) == {"malware", "apt-28", "c2"}

    

    def test_patch_with_invalid_labels_uppercase(self, stixify_file):
        data = {"labels": "malware,Invalid-Label,c2"}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert not serializer.is_valid()
        assert "labels" in serializer.errors

    def test_patch_with_invalid_labels_special_chars(self, stixify_file):
        data = {"labels": ["malware,label&underscore,c2"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert not serializer.is_valid()
        assert "labels" in serializer.errors

    def test_patch_with_single_label(self, stixify_file):
        data = {"labels": ["malware"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.labels == ["malware"]

    def test_patch_with_empty_labels(self, stixify_file):
        data = {"labels": []}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid()
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.labels == []

    def test_patch_with_numeric_labels(self, stixify_file):
        data = {"labels": ["test-123,malware-456"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert set(stixify_file.labels) == {"test-123", "malware-456"}


@pytest.mark.django_db
class TestFilePatchSerializerSources:
    def test_patch_with_valid_sources(self, stixify_file):
        data = {"sources": ["https://example.com,https://another.com/path"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert set(stixify_file.sources) == {"https://example.com", "https://another.com/path"}

    def test_patch_with_http_source(self, stixify_file):
        data = {"sources": ["http://example.com"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.sources == ["http://example.com"]

    def test_patch_with_invalid_sources_no_scheme(self, stixify_file):
        data = {"sources": ["example.com"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert not serializer.is_valid()
        assert "sources" in serializer.errors

    def test_patch_with_invalid_sources_malformed(self, stixify_file):
        data = {"sources": ["https://example.com,not-a-url"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert not serializer.is_valid()
        assert "sources" in serializer.errors

    def test_patch_with_empty_sources(self, stixify_file):
        data = {"sources": []}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid()
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.sources == [] or stixify_file.sources is None

    def test_patch_with_source_with_port(self, stixify_file):
        data = {"sources": ["https://example.com:8080/path"]}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.sources == ["https://example.com:8080/path"]


@pytest.mark.django_db
class TestFilePatchSerializerValidation:
    def test_patch_with_name_only(self, stixify_file):
        data = {"name": "New Name"}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid()
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.name == "New Name"

    def test_patch_with_labels_and_sources(self, stixify_file):
        data = {
            "labels": ["malware,c2"],
            "sources": ["https://example.com,https://another.com"]
        }
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        serializer.save()
        stixify_file.refresh_from_db()
        assert set(stixify_file.labels) == {"malware", "c2"}
        assert set(stixify_file.sources) == {"https://example.com", "https://another.com"}

    def test_patch_requires_at_least_one_field(self, stixify_file):
        data = {}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_patch_with_null_sources(self, stixify_file):
        data = {"sources": []}
        serializer = FilePatchSerializer(stixify_file, data=data, partial=True)
        assert serializer.is_valid()
        serializer.save()
        stixify_file.refresh_from_db()
        assert stixify_file.sources is None or stixify_file.sources == []


@pytest.mark.django_db
class TestFileSerializerLabels:
    def test_create_with_valid_labels(self, stixify_job):
        test_file = ContentFile(b"test content", name="test.txt")

        data = {
            "name": "Test File",
            "mode": "txt",
            "identity_id": str(stixify_job.file.identity.id),
            "profile_id": str(stixify_job.profile.id),
            "file": test_file,
            "labels": ["malware,apt-28,apt.group-28"],
        }
        serializer = FileSerializer(data=data)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"
        assert set(serializer.validated_data["labels"]) == {"malware", "apt-28", "apt.group-28"}

    def test_create_with_invalid_labels(self, stixify_job):
        test_file = ContentFile(b"test content", name="test.txt")

        data = {
            "name": "Test File",
            "mode": "txt",
            "identity_id": str(stixify_job.file.identity.id),
            "profile_id": str(stixify_job.profile.id),
            "file": test_file,
            "labels": "malware,apt.group.28",
        }
        serializer = FileSerializer(data=data)
        assert not serializer.is_valid()
        assert "labels" in serializer.errors


@pytest.mark.django_db
class TestFileSerializerSources:
    def test_create_with_valid_sources(self, stixify_job):
        test_file = ContentFile(b"test content", name="test.txt")

        data = {
            "name": "Test File",
            "mode": "txt",
            "identity_id": str(stixify_job.file.identity.id),
            "profile_id": str(stixify_job.profile.id),
            "file": test_file,
            "sources": ["https://example.com,https://another.com"],
        }
        serializer = FileSerializer(data=data)
        assert serializer.is_valid(), f"Expected valid but got errors: {serializer.errors}"

    def test_create_with_invalid_sources(self, stixify_job):
        test_file = ContentFile(b"test content", name="test.txt")

        data = {
            "name": "Test File",
            "mode": "txt",
            "identity_id": str(stixify_job.file.identity.id),
            "profile_id": str(stixify_job.profile.id),
            "file": test_file,
            "sources": ["not-a-url"],
        }
        serializer = FileSerializer(data=data)
        assert not serializer.is_valid()
        assert "sources" in serializer.errors


@pytest.mark.django_db
class TestReprocessFilesSerializer:
    def test_requires_file_ids_or_identity_id(self):
        serializer = ReprocessFilesSerializer(data={"skip_extraction": True})

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_rejects_reversed_added_range(self, stixify_file):
        serializer = ReprocessFilesSerializer(
            data={
                "file_ids": [str(stixify_file.id)],
                "skip_extraction": True,
                "added_after": "2026-08-02T00:00:00Z",
                "added_before": "2026-08-01T00:00:00Z",
            }
        )

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_accepts_file_ids_and_added_range(self, stixify_file):
        serializer = ReprocessFilesSerializer(
            data={
                "file_ids": [str(stixify_file.id)],
                "skip_extraction": True,
                "added_after": "2026-08-01T00:00:00Z",
                "added_before": "2026-08-02T00:00:00Z",
            }
        )

        assert serializer.is_valid(), serializer.errors
