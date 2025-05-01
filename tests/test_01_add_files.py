import io
import json
import os
import time
from types import SimpleNamespace
import unittest, pytest
from urllib.parse import urljoin

from tests.utils import remove_unknown_keys, wait_for_jobs

base_url = os.environ["SERVICE_BASE_URL"]
import requests
files_base_url = "https://pub-99019d5e65d44129a12bd0448a6b6e64.r2.dev/"

def all_posts():
    DATA = [
        {
            "profile_id": "fb83f69c-dcef-55e0-8f7d-768399e9326c",
            "mode": "pdf",
            "name": "some document",
            "file_name": "pdf-real/bitdefender-rdstealer.pdf",
            "report_id": "report--a378c839-0940-56fb-b52c-e5b78d34ec94",

            "identity": {
                "type": "identity",
                "id": "identity--a378c839-0940-56fb-b52c-e5b78d34ec94",
                "name": "identity meant for deletion",
                "identity_class": "individual",
                "spec_version":"2.1",
            },
        },
        {
            "profile_id": "64ca67f0-753a-51b5-a64b-de73184c5457",
            "mode": "md",
            "name": "some document 2",
            "file_name": "markdown/threat-report.md",
            "report_id": "report--a378c839-0940-56fb-b52c-e5b78d34ec94", # report_id already exists
            "should_fail": True,
        },
        {
            "profile_id": "64ca67f0-753a-51b5-a64b-de73184c5457",
            "mode": "md",
            "name": "some markdown document",
            "file_name": "markdown/threat-report.md",
        },
        {
            "profile_id": "64ca67f0-753a-51b5-a64b-de73184c5457",
            "mode": "html_article",
            "name": "Unit42 Ursa",
            "tlp_level": "red",
            "confidence": 34,
            "labels": [
                "label2"
            ],
            "file_name": "html-real/unit42-Fighting-Ursa-Luring-Targets-With-Car-for-Sale.html",
            "report_id": "report--cc2a723e-fc24-42d1-8ffc-2c76a5531512",
        },
        {
            "profile_id": "fb83f69c-dcef-55e0-8f7d-768399e9326c",
            "mode": "word",
            "name": "txt2stix local extractions docx",
            "tlp_level": "green",
            "confidence": 7,
            "labels": [
                "label1",
                "label2"
            ],
            "file_name": "doc/txt2stix-local-extractions.docx",
            "report_id": "report--2bd196b5-cc59-491d-99ee-ed5ea2002d61",
        },
    ]
    return [[d.pop("file_name"), d, d.get("should_fail")] for d in DATA]


@pytest.mark.parametrize(
    ["file_name", "file_data", "should_fail"], all_posts()
)
def test_add_file(file_name, file_data: dict, should_fail):
    file_url = urljoin(files_base_url, file_name)
    f = io.BytesIO(requests.get(file_url).content)
    f.name = os.path.basename(file_name)
    payload = file_data.copy()
    if identity := payload.get('identity'):
        payload.update(identity=json.dumps(identity))
    file_job_resp = requests.post(
        urljoin(base_url, f"api/v1/files/"), data=payload, files={'file': (f.name, f, "application/pdf")})

    if should_fail:
        assert file_job_resp.status_code == 400, "add file request expected to fail"
        return

    assert file_job_resp.status_code == 201, f"request failed: {file_job_resp.text}"
    file_job_resp_data = file_job_resp.json()

    job_file_data = file_job_resp_data['file']
    if report_id := file_data.get('report_id'):
        expected_id = report_id.split('--')[-1]
        assert job_file_data['id'] == expected_id, "report_id in POST body not respected"
    assert job_file_data['id'] == job_file_data['report_id'].split('--')[-1], "file.report_id must match file.id"

    job_data = wait_for_jobs(file_job_resp_data['id'])
    assert job_file_data['profile_id'] == file_data['profile_id']

    for k in job_file_data:
        if k in file_data:
            assert job_file_data[k] == file_data[k], f"property {k} in output does not match sent data"
