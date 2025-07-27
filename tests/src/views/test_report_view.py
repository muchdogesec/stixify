from stixify.web import models
from stixify.web.serializers import FileSerializer, JobSerializer
from stixify.web.views import FileView
import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
import io
from dogesec_commons.objects.db_view_creator import startup_func


from functools import lru_cache
import time
from django.conf import settings
from django.http import HttpRequest
import rest_framework.request
import pytest
from dogesec_commons.objects.helpers import ArangoDBHelper
from stix2arango.stix2arango import Stix2Arango
import contextlib
from arango.client import ArangoClient

from tests.src.views import bundles
from tests.utils import Transport


def as_arango2stix_db(db_name):
    if db_name.endswith("_database"):
        return "_".join(db_name.split("_")[:-1])
    return db_name


@contextlib.contextmanager
def make_s2a_uploads(
    uploads: list[list[dict]],
    database=settings.ARANGODB_DATABASE,
    **kwargs,
):
    database = as_arango2stix_db(database)
    s2a = Stix2Arango(
        database=database,
        collection="stixify",
        file="",
        host_url=settings.ARANGODB_HOST_URL,
        **kwargs,
    )
    startup_func()
    for bundle in uploads:
        for obj in bundle["objects"]:
            obj["_stixify_report_id"] = bundle["id"].replace("bundle", "report")
        s2a.run(data=bundle)
    time.sleep(1)
    yield s2a



@pytest.fixture(autouse=True, scope="package")
def upload_arango_objects():
    with make_s2a_uploads(
        [
            bundles.BUNDLE_1,
            bundles.BUNDLE_2,
        ],
    ):
        return


@pytest.mark.parametrize(
    "report_id",
    [
        "report--52d2146c-798a-440f-942f-6fe039fb8995",
        "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
    ],
)
def test_retrieve(client, report_id, api_schema):
    resp = client.get(f"/api/v1/reports/{report_id}/")
    assert resp.status_code == 200
    assert resp.data["id"] == report_id
    api_schema['/api/v1/reports/{report_id}/']['GET'].validate_response(Transport.get_st_response(resp))



@pytest.mark.parametrize(
    "report_id",
    [
        "52d2146c-798a-440f-942f-6fe039fb8995",
        "report--ed758a1b-abcd-4fca-8178-0c30d93a03ab",
    ],
)
def test_retrieve_bad_kwargs(client, report_id, api_schema):
    resp = client.get(f"/api/v1/reports/{report_id}/")
    assert resp.status_code == 404
    api_schema['/api/v1/reports/{report_id}/']['GET'].validate_response(Transport.get_st_response(resp))


def test_list(client, api_schema):
    resp = client.get(f"/api/v1/reports/")
    assert resp.status_code == 200
    assert resp.data["total_results_count"] == 2
    assert len(resp.data["objects"]) == 2
    api_schema['/api/v1/reports/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.parametrize(
    "report_id,expected_ids",
    [
        (
            "report--52d2146c-798a-440f-942f-6fe039fb8995",
            [
                "ipv4-addr--de3da98b-98d0-56a3-af1d-9a740df60c7b",
                "relationship--27cbbba6-6b9d-5748-97cc-deaa4dcc2f9a",
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
                "indicator--dd695028-06bc-5a67-8f4c-b572916f925e",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "domain-name--a9847407-cfa9-58ea-aa81-5ecc25c0a464",
                "relationship--a582943e-e5cf-598c-b8f9-52037eb06f2c",
                "indicator--34c99f8e-a858-54e7-a457-4852a98f03ab",
                "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        ),
        (
            "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            [
                "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
                "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
                "relationship--81a3e593-b36f-5da8-bc98-8e8b92e1730b",
                "indicator--21c8753d-a681-5159-949d-72d6b1fefb89",
                "domain-name--791a1b67-147a-568f-b515-b4184f3d48f3",
                "indicator--7a95323c-c59e-5e10-8edc-a24f5001b58e",
            ],
        ),
    ],
)
def test_report_objects(client, report_id, expected_ids, api_schema):
    resp = client.get(f"/api/v1/reports/{report_id}/objects/")
    assert resp.status_code == 200
    assert {obj["id"] for obj in resp.data["objects"]} == set(expected_ids)
    api_schema['/api/v1/reports/{report_id}/objects/']['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.parametrize(
    "report_id,visible_to,expects_result",
    [
        (
            "report--52d2146c-798a-440f-942f-6fe039fb8995",  # clear
            "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            True,
        ),
        (
            "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",  # amber
            "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            False,
        ),
        (
            "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",  # amber
            "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            True,
        ),
        (
            "report--52d2146c-798a-440f-942f-6fe039fb8995",  # clear
            "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            True,
        ),
    ],
)
def test_report_objects_visible_to(client, report_id, visible_to, expects_result, api_schema):
    resp = client.get(
        f"/api/v1/reports/{report_id}/objects/",
        query_params=dict(visible_to=visible_to),
    )
    assert resp.status_code == 200
    if expects_result:
        assert resp.data["total_results_count"] > 0
    else:
        assert resp.data["total_results_count"] == 0
    api_schema["/api/v1/reports/{report_id}/objects/"]['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.parametrize(
    "report_id,types",
    [
        (
            "report--52d2146c-798a-440f-942f-6fe039fb8995",  # clear
            "identity",
        ),
        (
            "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",  # amber
            "identity,marking-definition",
        ),
        (
            "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",  # amber
            "indicator,marking-definition",
        ),
    ],
)
def test_report_objects_types(client, report_id, types, api_schema):
    resp = client.get(
        f"/api/v1/reports/{report_id}/objects/", query_params=dict(types=types)
    )
    assert resp.status_code == 200
    assert {obj["type"] for obj in resp.data["objects"]} == set(types.split(","))
    assert resp.data["total_results_count"] > 0
    api_schema["/api/v1/reports/{report_id}/objects/"]['GET'].validate_response(Transport.get_st_response(resp))


@pytest.mark.parametrize(
    "filters,expected_ids",
    [
        (
            dict(identity="identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30"),
            ["report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"],
        ),
        (
            dict(visible_to="identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30"),
            [
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
            ],
        ),
        (
            dict(visible_to="identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"),
            ["report--52d2146c-798a-440f-942f-6fe039fb8995"],
        ),
        (
            dict(),
            [
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
            ],
        ),
        (dict(name="bad name"), []),
        (dict(name="rig"), ["report--52d2146c-798a-440f-942f-6fe039fb8995"]),
        (dict(name="oThER"), ["report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"]),
        (dict(tlp_level="clear", name="other"), []),
        (dict(tlp_level="amber"), ["report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"]),
        (dict(labels="ploit"), ["report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"]),
        (dict(labels="steal"), ["report--52d2146c-798a-440f-942f-6fe039fb8995"]),
        (
            dict(ai_incident_classification="infostealer"),
            ["report--52d2146c-798a-440f-942f-6fe039fb8995"],
        ),
        (
            dict(ai_incident_classification="infostealer,cyber_crime"),
            [
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            ],
        ),
        (
            dict(
                ai_incident_classification="infostealer,cyber_crime", confidence_min=80
            ),
            [
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
            ],
        ),
        (
            dict(
                ai_incident_classification="infostealer,cyber_crime", confidence_min=17
            ),
            [
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            ],
        ),
        (
            dict(created_min="2022-08-11T15:18:11.499288Z"),
            [
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            ],
        ),
        (
            dict(created_min="2022-08-10"),
            [
                "report--52d2146c-798a-440f-942f-6fe039fb8995",
                "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            ],
        ),
        (
            dict(created_max="2022-08-19"),
            ["report--52d2146c-798a-440f-942f-6fe039fb8995"],
        ),
        (dict(created_max="2022-08-19", created_min="2022-08-13"), []),
        (
            dict(created_min="2022-08-13", created_max="2026-08-19"),
            ["report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"],
        ),
    ],
)
def test_list_filters(client, filters, expected_ids, api_schema):
    resp = client.get(f"/api/v1/reports/", query_params=filters)
    assert resp.status_code == 200
    assert {obj["id"] for obj in resp.data["objects"]} == set(expected_ids)
    api_schema["/api/v1/reports/"]['GET'].validate_response(Transport.get_st_response(resp))
