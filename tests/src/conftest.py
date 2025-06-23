import os
import pytest
import os
from django.conf import settings
from arango.client import ArangoClient
from dogesec_commons.stixifier.models import Profile
from unittest.mock import patch

import pytest
from dogesec_commons.utils import Pagination, Ordering
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from stixify.web import models
from django.core.files.uploadedfile import SimpleUploadedFile


def pytest_sessionstart():
    client = ArangoClient(hosts=settings.ARANGODB_HOST_URL)
    sys_db = client.db(
        "_system",
        username=settings.ARANGODB_USERNAME,
        password=settings.ARANGODB_PASSWORD,
    )
    db_name: str = settings.ARANGODB_DATABASE + "_database"
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    db = client.db(
        db_name,
        username=settings.ARANGODB_USERNAME,
        password=settings.ARANGODB_PASSWORD,
    )
    for c in db.collections():
        c_name = c["name"]
        if c_name.endswith("_collection"):
            db.collection(c_name).truncate()


@pytest.fixture
def stixifier_profile():
    profile = Profile.objects.create(
        name="test-profile",
        extractions=["pattern_host_name", "pattern_ipv4_address"],
        extract_text_from_image=False,
        defang=True,
        relationship_mode="standard",
        ai_settings_relationships=None,
        ai_settings_extractions=[],
        ai_content_check_provider=None,
        ai_summary_provider=None,
        ai_create_attack_flow=False,
        id="26fce5ea-c3df-45a2-8989-0225549c704b",
    )
    yield profile


@pytest.fixture
def stixify_file(stixifier_profile):
    return models.File.objects.create(
        id="dcbeb240-8dd6-4892-8e9e-7b6bda30e454",
        file=SimpleUploadedFile("file.md", b"File Content", "text/markdown"),
        profile=stixifier_profile,
        mode="md",
        name="First file, not special",
        identity={
            "type": "identity",
            "id": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T14:26:48.932Z",
            "modified": "2025-06-17T14:26:48.932Z",
            "name": "dummy identity",
            "identity_class": "individual",
        },
    )


@pytest.fixture
def stixify_job(stixify_file):
    job = models.Job.objects.create(
        file=stixify_file, id="164716d9-85af-4a81-8f71-9168db3fadf0"
    )
    return job
