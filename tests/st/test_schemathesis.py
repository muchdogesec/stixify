import time
from unittest.mock import patch
from urllib.parse import urlencode
import uuid
import schemathesis
import pytest
from schemathesis.core.transport import Response as SchemathesisResponse
from stixify.wsgi import application as wsgi_app
from rest_framework.response import Response as DRFResponse
from hypothesis import settings
from hypothesis import strategies
from schemathesis.specs.openapi.checks import negative_data_rejection, positive_data_acceptance
from schemathesis.config import GenerationConfig

schema = schemathesis.openapi.from_wsgi("/api/schema/?format=json", wsgi_app)
schema.config.base_url = "http://localhost:8004/"
schema.config.generation = GenerationConfig(allow_x00=False)

file_ids = strategies.sampled_from([uuid.uuid4() for _ in range(3)]+["dcbeb240-8dd6-4892-8e9e-7b6bda30e454"])
job_ids  = strategies.sampled_from([uuid.uuid4() for _ in range(3)]+["164716d9-85af-4a81-8f71-9168db3fadf0"])
profile_ids  = strategies.sampled_from([uuid.uuid4() for _ in range(3)]+["26fce5ea-c3df-45a2-8989-0225549c704b"])


@pytest.fixture(autouse=True)
def override_transport(monkeypatch):
    ## patch transport.get
    from schemathesis import transport
    from tests.utils import Transport
    monkeypatch.setattr(transport, "get", lambda _: Transport())


@pytest.fixture(autouse=True)
def module_setup(stixifier_profile, stixify_job):
    yield

@pytest.mark.django_db(transaction=True)
@schema.given(
    post_id=file_ids,
    profile_id=profile_ids,
    job_id=job_ids
)
@schema.exclude(method=["POST"]).exclude(method="DELETE", path="/api/v1/profiles/{profile_id}/").parametrize()
def test_api(case: schemathesis.Case, **kwargs):
    for k, v in kwargs.items():
        if k in case.path_parameters:
            case.path_parameters[k] = v
    case.call_and_validate(excluded_checks=[negative_data_rejection, positive_data_acceptance])


@pytest.mark.django_db(transaction=True)
@schema.given(
    post_id=file_ids,
    profile_id=profile_ids,
    job_id=job_ids
)
@schema.include(method=["POST"]).parametrize()
def test_upload(case: schemathesis.Case, **kwargs):
    for k, v in kwargs.items():
        if k in case.path_parameters:
            case.path_parameters[k] = v
    case.call_and_validate(excluded_checks=[negative_data_rejection, positive_data_acceptance])
