from datetime import UTC, datetime
import os
import time
from types import SimpleNamespace
import unittest, pytest
from urllib.parse import urljoin
from dateutil.parser import parse as parse_date

from tests.utils import remove_unknown_keys, wait_for_jobs

base_url = os.environ["SERVICE_BASE_URL"]
import requests
@pytest.mark.parametrize(
        ["file_id", "expected_image_count"],
        [
            ["2bd196b5-cc59-491d-99ee-ed5ea2002d61", 0],
            ["cc2a723e-fc24-42d1-8ffc-2c76a5531512", 4],
            ["a378c839-0940-56fb-b52c-e5b78d34ec94", 5],
        ]
)

def test_image_extraction(file_id, expected_image_count):
    file_url = urljoin(base_url, f"api/v1/files/{file_id}/images/")
    get_resp = requests.get(file_url)
    data = get_resp.json()
    assert data['total_results_count'] == expected_image_count