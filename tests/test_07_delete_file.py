

import os
import time
from types import SimpleNamespace
import unittest, pytest
from urllib.parse import urljoin

from tests.utils import remove_unknown_keys, wait_for_jobs

base_url = os.environ["SERVICE_BASE_URL"]
import requests

@pytest.mark.parametrize(
    ["file_id", "should_fail"],
    [
        ["8f89731d-b9de-5931-9182-5460af59ca84", True], #post does not exist
        ["cc2a723e-fc24-42d1-8ffc-2c76a5531512", False],
        ["cc2a723e-fc24-42d1-8ffc-2c76a5531512", True], #post already deleted
    ]
)
def test_delete_file(file_id, should_fail, subtests):
    file_url = urljoin(base_url, f"api/v1/files/{file_id}/")
    delete_resp = requests.delete(file_url)

    if should_fail:
        assert delete_resp.status_code == 404, f"delete post request expected to fail: {delete_resp.text}"
        return
    assert delete_resp.status_code == 204, f"unexpected status, body: {delete_resp.text}"


    get_resp = requests.get(file_url)
    assert get_resp.status_code == 404, f"post should already be deleted"

    with subtests.test('test_delete_report_deletes_objects', file_id=file_id):
        does_delete_file_delete_report(file_id)


def does_delete_file_delete_report(file_id):
    time.sleep(3)
    report_id = f"report--{file_id}"
    report_url = urljoin(base_url, f"api/v1/objects/{report_id}/")
    resp = requests.get(report_url)
    assert resp.status_code == 200
    data = resp.json()
    assert data['total_results_count'] == 0, "report should already be deleted"

    report_objects_gone(report_id)

def report_objects_gone(report_id):
    report_url = urljoin(base_url, f"api/v1/reports/{report_id}/objects/")
    get_resp = requests.get(report_url)
    assert get_resp.status_code == 200
    assert get_resp.json()['total_results_count'] == 0
