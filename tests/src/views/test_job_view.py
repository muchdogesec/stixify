import pytest

from stixify.web import models
from tests.utils import Transport


@pytest.mark.parametrize(
    "states,expected_ids",
    [
        (["pending"], {"9e0d79ed-94d9-42a3-aa41-4772ae922176"}),
        (["processing"], {"2583d09b-6535-4f15-9fd1-5dcb55230f08"}),
        (
            ["pending", "processing"],
            {
                "9e0d79ed-94d9-42a3-aa41-4772ae922176",
                "2583d09b-6535-4f15-9fd1-5dcb55230f08",
            },
        ),
        (["failed"], {"0014c5a1-7a5e-408f-88ea-83ec5a1b8af1"}),
        (["completed"], set()),
        (
            [],
            {
                "9e0d79ed-94d9-42a3-aa41-4772ae922176",
                "2583d09b-6535-4f15-9fd1-5dcb55230f08",
                "0014c5a1-7a5e-408f-88ea-83ec5a1b8af1",
            },
        ),
    ],
)
@pytest.mark.django_db
def test_jobs_filter_by_multiple_states(client, api_schema, states, expected_ids):
    models.Job.objects.create(
        id="9e0d79ed-94d9-42a3-aa41-4772ae922176",
        type=models.JobType.IMPORT_FILE,
        state=models.JobState.PENDING,
    )
    models.Job.objects.create(
        id="2583d09b-6535-4f15-9fd1-5dcb55230f08",
        type=models.JobType.BUILD_EMBEDDINGS,
        state=models.JobState.PROCESSING,
    )
    models.Job.objects.create(
        id="0014c5a1-7a5e-408f-88ea-83ec5a1b8af1",
        type=models.JobType.SYNC_VULNERABILITIES,
        state=models.JobState.FAILED,
    )

    resp = client.get(f"/api/v1/jobs/?state={','.join(states)}")
    assert resp.status_code == 200
    assert resp.data["total_results_count"] == len(expected_ids)

    returned = {item["id"] for item in resp.data["jobs"]}
    assert returned == expected_ids

    api_schema["/api/v1/jobs/"]["GET"].validate_response(
        Transport.get_st_response(resp)
    )