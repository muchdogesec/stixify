from stixify.web import models
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.fixture
def more_files(stixifier_profile, identity):
    return [
        models.File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("file1.txt", b"File Content 1", "text/markdown"),
            profile=stixifier_profile,
            mode="md",
            ai_describes_incident=True,
            name="First file, special",
            identity=identity,
        ),
        models.File.objects.create(
            id="aadbe23d-192c-488d-8ce9-96aa2613453f",
            file=SimpleUploadedFile("file2.txt", b"File Content 2", "text/markdown"),
            profile=stixifier_profile,
            mode="txt",
            ai_incident_classification=["other", "apt_group", "data_leak"],
            name="second file, not breakable",
            identity=identity,
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
            identity=identity,
        ),
    ]
