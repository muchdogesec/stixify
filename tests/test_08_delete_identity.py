

import os
import time
from types import SimpleNamespace
import unittest, pytest
from urllib.parse import urljoin

from tests.test_07_delete_file import does_delete_file_delete_report
from tests.utils import remove_unknown_keys, wait_for_jobs

base_url = os.environ["SERVICE_BASE_URL"]
import requests

@pytest.mark.parametrize(
    ["identity_uuid"],
    [
        ["a378c839-0940-56fb-b52c-e5b78d34ec94"]
    ]
)
def test_delete_identity(identity_uuid, subtests):
    identity_url = urljoin(base_url, f"api/v1/identities/identity--{identity_uuid}/")
    file_url = urljoin(base_url, f"api/v1/files/{identity_uuid}/")
    delete_resp = requests.delete(identity_url)

    assert delete_resp.status_code == 204, f"unexpected status, body: {delete_resp.text}"
    time.sleep(2)
    get_resp = requests.get(identity_url)
    assert get_resp.status_code == 200
    assert len(get_resp.json()['objects']) == 0, f"identity should already be deleted"


    get_resp = requests.get(file_url)
    assert get_resp.status_code == 404, f"file should already be deleted"

    with subtests.test('test_delete_identity_deletes_objects', file_id=identity_uuid):
        does_delete_file_delete_report(identity_uuid)
