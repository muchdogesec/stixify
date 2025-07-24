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
def override_transport(monkeypatch, client):
    from schemathesis.transport.wsgi import WSGI_TRANSPORT, WSGITransport

    class Transport(WSGITransport):
        def __init__(self):
            super().__init__()
            self._copy_serializers_from(WSGI_TRANSPORT)

        @staticmethod
        def case_as_request(case):
            from schemathesis.transport.requests import REQUESTS_TRANSPORT
            import requests

            r_dict = REQUESTS_TRANSPORT.serialize_case(
                case,
                base_url=case.operation.base_url,
            )
            return requests.Request(**r_dict).prepare()

        def send(self, case: schemathesis.Case, *args, **kwargs):
            t = time.time()
            case.headers.pop("Authorization", "")
            serialized_request = WSGI_TRANSPORT.serialize_case(case)
            serialized_request.update(
                QUERY_STRING=urlencode(serialized_request["query_string"])
            )
            response: DRFResponse = client.generic(**serialized_request)
            elapsed = time.time() - t
            return SchemathesisResponse(
                response.status_code,
                headers={k: [v] for k, v in response.headers.items()},
                content=response.content,
                request=self.case_as_request(case),
                elapsed=elapsed,
                verify=True,
            )

    ## patch transport.get
    from schemathesis import transport

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
@schema.exclude(method=["POST", "PATCH"]).parametrize()
@settings(max_examples=30)
def test_api(case: schemathesis.Case, **kwargs):
    for k, v in kwargs.items():
        if k in case.path_parameters:
            case.path_parameters[k] = v
    case.call_and_validate(excluded_checks=[negative_data_rejection, positive_data_acceptance])
