import os
import random
import time
from types import SimpleNamespace
import unittest, pytest
from urllib.parse import urljoin

from tests.utils import remove_unknown_keys, wait_for_jobs

base_url = os.environ["SERVICE_BASE_URL"]
import requests


@pytest.mark.parametrize(
    ["filters", "expected_ids"],
    [
        [
            dict(name="local extractions"),
            [
                "2bd196b5-cc59-491d-99ee-ed5ea2002d61",
            ],
        ],  # feed does not exist
        [
            dict(mode="html_article"),
            [
                "cc2a723e-fc24-42d1-8ffc-2c76a5531512",
            ],
        ],
        [
            dict(profile_id="fb83f69c-dcef-55e0-8f7d-768399e9326c"),
            [
                "a378c839-0940-56fb-b52c-e5b78d34ec94",
                "2bd196b5-cc59-491d-99ee-ed5ea2002d61",

            ],
        ],

        [
            dict(id="2bd196b5-cc59-491d-99ee-ed5ea2002d61,a378c839-0940-56fb-b52c-e5b78d34ec94,cc2a723e-fc24-42d1-8ffc-2c76a5531512"),
            [
                "a378c839-0940-56fb-b52c-e5b78d34ec94",
                "2bd196b5-cc59-491d-99ee-ed5ea2002d61",
                "cc2a723e-fc24-42d1-8ffc-2c76a5531512",
            ],
        ],
    ],
)
def test_filters_generic(filters: dict, expected_ids: list[str]):
    expected_ids = set(expected_ids)
    url = urljoin(base_url, "api/v1/files/")
    resp = requests.get(url, params=filters)
    resp_data = resp.json()
    assert resp_data["total_results_count"] == len(expected_ids)
    assert {file["id"] for file in resp_data["files"]} == expected_ids


def random_posts_values(key, count):
    url = urljoin(base_url, "api/v1/files/")
    resp = requests.get(url)
    data = resp.json()
    return [post[key] for post in random.choices(data["files"], k=count)]


def more_created_filters(count):
    filters = []
    createds = random_posts_values("created", 50)
    for i in range(count):
        mmin = mmax = None
        if random.random() > 0.7:
            mmax = random.choice(createds)
        if random.random() < 0.3:
            mmin = random.choice(createds)
        if mmin or mmax:
            filters.append([mmin, mmax])
    return filters

def created_minmax_test(created_min, created_max):
    filters = {}
    if created_min:
        filters.update(created_min=created_min)
    if created_max:
        filters.update(created_max=created_max)

    assert created_max or created_min, "at least one of two filters required"

    url = urljoin(base_url, "api/v1/files/")
    resp = requests.get(url, params=filters)
    assert resp.status_code == 200
    resp_data = resp.json()
    for d in resp_data["files"]:
        if created_min:
            assert (
                d["created"] >= created_min
            ), "created must not be less than created_min" + f"{[f['created'] for f in resp_data['files']]}"
        if created_max:
            assert (
                d["created"] <= created_max
            ), "created must not be greater than created_max" + f"{[f['created'] for f in resp_data['files']]}"


def test_extra_created_filters(subtests):
    for dmin, dmax in more_created_filters(22):
        with subtests.test(
            "randomly_generated created_* query", created_min=dmin, created_max=dmax
        ):
            created_minmax_test(dmin, dmax)