import random
import time
from urllib.parse import urlparse, parse_qs
from arango.client import ArangoClient
from django.conf import settings
from unittest.mock import patch
import pytest
import uuid
from dogesec_commons.objects.helpers import ArangoDBHelper

from stixify.worker import helpers
from stixify.web import models

STIXIFY_COLLECTION = "stixify_vertex_collection"


@pytest.fixture(autouse=True, scope='module')
def stixify_db():
    helper = ArangoDBHelper("", None)

    helper.db.collection(STIXIFY_COLLECTION).insert_many(
        FAKE_VULNERABILITIES, raise_on_document_error=True
    )
    yield helper.db
    helper.db.collection(STIXIFY_COLLECTION).truncate()
    helper.db.collection(STIXIFY_COLLECTION).truncate()


VULNS = [
    ("CVE-2011-2462", "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a"),
    ("CVE-2015-0816", "vulnerability--0d92bd85-e2f0-51ec-9773-6cf161498e25"),
    ("CVE-2018-15982", "vulnerability--71706d20-55df-5004-b315-7d696842447e"),
    ("CVE-2024-38475", "vulnerability--59a383f8-f6a6-5871-9fe0-75abbdf676c8"),
    ("CVE-2022-26318", "vulnerability--75a5ba93-b53c-5abf-9c88-75846041cffe"),
    ("CVE-2020-7961", "vulnerability--906fd5ca-f2a6-5dfc-8f4a-2b493c3650ac"),
    ("CVE-2020-8515", "vulnerability--def77e14-20ca-557f-9757-cc0c4147dcd3"),
    ("CVE-2020-8644", "vulnerability--0039762d-8523-514e-bce6-3103e1724b4f"),
    ("CVE-2020-25506", "vulnerability--48ac0edb-984a-55e3-94aa-017c696366b5"),
    ("CVE-2020-26919", "vulnerability--0957b9de-2d8b-5f8b-817d-6a34b7b7f10a"),
]
FAKE_VULNERABILITIES = [
    dict(
        _key=id + "+" + str(index),
        name=name,
        type="vulnerability",
        id=id,
        _md5_hash=id + str(index),
    )
    for name, id in VULNS
    for index in range(10)
]


@pytest.fixture
def fake_retriever():
    def fake_retrieve(url):
        qs = parse_qs(urlparse(url).query)
        cve_list = qs.get("cve_id", [""])[0].split(",") if qs.get("cve_id") else []
        return [
            {"name": name, "dummy": "info", "extra": "extra", "id": "random"}
            for name in cve_list
            if name
        ]

    with patch(
        "stixify.worker.helpers.STIXObjectRetriever._retrieve_objects",
        side_effect=fake_retrieve,
    ):
        yield


@pytest.mark.django_db
def test_get_vulnerabilities(stixify_db):
    r1 = helpers.get_vulnerabilities(STIXIFY_COLLECTION)
    assert r1 == {
        name: [id + "+" + str(index) for index in range(10)] for name, id in VULNS
    }
    assert len(r1) == 10
    assert len(r1["CVE-2011-2462"]) == 10


@pytest.mark.django_db
def test_get_updates(fake_retriever):
    vulnerabilities = {
        "CVE-2011-2462": [
            "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+2",
            "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+4",
            "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+8",
            "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+9",
        ],
        "CVE-2015-0816": [
            "vulnerability--0d92bd85-e2f0-51ec-9773-6cf161498e25+0",
        ],
    }
    now = time.time()

    r1 = list(helpers.get_updates(vulnerabilities, now))
    assert r1 == [
        {
            "_key": "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+2",
            "name": "CVE-2011-2462",
            "dummy": "info",
            "extra": "extra",
            "_stixify_updated_on": now,
        },
        {
            "_key": "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+4",
            "name": "CVE-2011-2462",
            "dummy": "info",
            "extra": "extra",
            "_stixify_updated_on": now,
        },
        {
            "_key": "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+8",
            "name": "CVE-2011-2462",
            "dummy": "info",
            "extra": "extra",
            "_stixify_updated_on": now,
        },
        {
            "_key": "vulnerability--74ebaaf5-7210-5422-94f5-3464d0db6e1a+9",
            "name": "CVE-2011-2462",
            "dummy": "info",
            "extra": "extra",
            "_stixify_updated_on": now,
        },
        {
            "_key": "vulnerability--0d92bd85-e2f0-51ec-9773-6cf161498e25+0",
            "name": "CVE-2015-0816",
            "dummy": "info",
            "extra": "extra",
            "_stixify_updated_on": now,
        },
    ]


@pytest.mark.django_db
def test_run_on_collections(stixify_db, fake_retriever):
    job = models.Job.objects.create(
        id=uuid.uuid4(),
        type=models.JobType.SYNC_VULNERABILITIES,
        state=models.JobState.PROCESSING,
    )
    r1 = helpers.run_on_collections(job, batch_size=5)
    job.refresh_from_db()
    assert r1 is None
    f = stixify_db.collection(STIXIFY_COLLECTION).find(dict(type="vulnerability"))
    assert job.extra["unique_vulnerabilities"] == 10
    assert job.extra["document_count"] == 100
    assert job.extra["processed_documents"] == 100
