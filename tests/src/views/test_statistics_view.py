"""
Tests for the Statistics endpoint (GET /api/v1/statistics/).

Verifies that:
- The response shape contains both last_7_days and last_30_days periods.
- Each period has the expected categories with correct knowledgebase values.
- Counts reflect only object values whose files were modified within the period window.
- Objects outside the time window are not counted.
- The top-10 ordering is by descending count.
"""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from stixify.web.models import File, ObjectValue


EXPECTED_CATEGORIES = ["enterprise-attack", "cve", "sector", "cwe"]
STATISTICS_URL = "/api/v1/statistics/"


def _make_file(profile, identity, *, file_id, name, modified_at):
    file_obj = File.objects.create(
        id=file_id,
        file=SimpleUploadedFile(f"{name}.md", b"stats file content", "text/markdown"),
        profile=profile,
        identity=identity,
        mode="md",
        name=name,
        summary="stats test post",
    )
    # Statistics windows are based on File.modified.
    File.objects.filter(pk=file_obj.pk).update(modified=modified_at)
    file_obj.refresh_from_db()
    return file_obj


@pytest.fixture
def stats_data(stixifier_profile, identity):
    """
    Creates files spread across three time windows:
      - within_7d  : 3 and 5 days ago  -> inside both 7-day and 30-day windows
      - within_30d : 20 days ago       -> inside 30-day window only
      - outside    : 40 days ago       -> outside both windows

    ObjectValues created:
      - "enterprise-attack" stix_id A: files within_7d[0], within_7d[1], within_30d[0]
        -> 7-day count=2, 30-day count=3
      - "enterprise-attack" stix_id B: file within_7d[0]
        -> 7-day count=1, 30-day count=1
      - "cve" stix_id C: file within_7d[0]
        -> 7-day count=1, 30-day count=1
      - "sector" stix_id D: file within_30d[0]
        -> 7-day count=0 (absent), 30-day count=1
      - "cwe" stix_id E: file outside[0]
        -> 7-day count=0 (absent), 30-day count=0 (absent)
    """
    now = timezone.now()

    file_7a = _make_file(
        stixifier_profile,
        identity,
        file_id="b0f14001-8ec5-4f7d-b078-dafd39f5b001",
        name="7d-file-a",
        modified_at=now - timedelta(days=3),
    )
    file_7b = _make_file(
        stixifier_profile,
        identity,
        file_id="b0f14001-8ec5-4f7d-b078-dafd39f5b002",
        name="7d-file-b",
        modified_at=now - timedelta(days=5),
    )
    file_30a = _make_file(
        stixifier_profile,
        identity,
        file_id="b0f14001-8ec5-4f7d-b078-dafd39f5b003",
        name="30d-file-a",
        modified_at=now - timedelta(days=20),
    )
    file_old = _make_file(
        stixifier_profile,
        identity,
        file_id="b0f14001-8ec5-4f7d-b078-dafd39f5b004",
        name="old-file",
        modified_at=now - timedelta(days=40),
    )

    for file_obj in [file_7a, file_7b, file_30a]:
        ObjectValue.objects.create(
            stix_id="attack-pattern--aaaaaaaa-0000-0000-0000-000000000001",
            type="attack-pattern",
            knowledgebase="enterprise-attack",
            values={"name": "Technique A", "aliases": ["T9000"]},
            file=file_obj,
            created=now,
            modified=now,
        )

    ObjectValue.objects.create(
        stix_id="attack-pattern--bbbbbbbb-0000-0000-0000-000000000002",
        type="attack-pattern",
        knowledgebase="enterprise-attack",
        values={"name": "Technique B", "aliases": ["T9001"]},
        file=file_7a,
        created=now,
        modified=now,
    )

    ObjectValue.objects.create(
        stix_id="vulnerability--cccccccc-0000-0000-0000-000000000003",
        type="vulnerability",
        knowledgebase="cve",
        values={"name": "CVE-2099-99999"},
        file=file_7a,
        created=now,
        modified=now,
    )

    ObjectValue.objects.create(
        stix_id="identity--dddddddd-0000-0000-0000-000000000004",
        type="identity",
        knowledgebase="sector",
        values={"name": "Finance"},
        file=file_30a,
        created=now,
        modified=now,
    )

    ObjectValue.objects.create(
        stix_id="weakness--eeeeeeee-0000-0000-0000-000000000005",
        type="weakness",
        knowledgebase="cwe",
        values={"name": "CWE-79"},
        file=file_old,
        created=now,
        modified=now,
    )

    return {"files": {"7a": file_7a, "7b": file_7b, "30a": file_30a, "old": file_old}}


@pytest.mark.django_db
class TestStatisticsView:

    def test_response_200(self, client, stats_data):
        """Endpoint returns HTTP 200."""
        response = client.get(STATISTICS_URL)
        assert response.status_code == 200

    def test_top_level_keys(self, client, stats_data):
        """Response has exactly last_7_days and last_30_days keys."""
        data = client.get(STATISTICS_URL).json()
        assert set(data.keys()) == {"last_7_days", "last_30_days"}

    def test_period_shape(self, client, stats_data):
        """Each period object has the expected keys."""
        data = client.get(STATISTICS_URL).json()
        for key in ("last_7_days", "last_30_days"):
            period = data[key]
            assert "period_days" in period
            assert "period_start" in period
            assert "period_end" in period
            assert "categories" in period

    def test_period_days_values(self, client, stats_data):
        """period_days matches the expected number of days."""
        data = client.get(STATISTICS_URL).json()
        assert data["last_7_days"]["period_days"] == 7
        assert data["last_30_days"]["period_days"] == 30

    def test_categories_present(self, client, stats_data):
        """All expected knowledgebase categories are present in each period."""
        data = client.get(STATISTICS_URL).json()
        for key in ("last_7_days", "last_30_days"):
            knowledgebases = [category["knowledgebase"] for category in data[key]["categories"]]
            for expected in EXPECTED_CATEGORIES:
                assert expected in knowledgebases, f"{expected} missing from {key}"

    def test_category_shape(self, client, stats_data):
        """Each category entry has label, knowledgebase, and results keys."""
        data = client.get(STATISTICS_URL).json()
        for category in data["last_7_days"]["categories"]:
            assert "label" in category
            assert "knowledgebase" in category
            assert "results" in category

    def test_result_entry_shape(self, client, stats_data):
        """Each result entry has stix_id, values, and count."""
        data = client.get(STATISTICS_URL).json()
        for period in ("last_7_days", "last_30_days"):
            for category in data[period]["categories"]:
                for result in category["results"]:
                    assert "stix_id" in result
                    assert "values" in result
                    assert "count" in result

    def _get_category(self, data, period_key, knowledgebase):
        return next(
            category
            for category in data[period_key]["categories"]
            if category["knowledgebase"] == knowledgebase
        )

    def test_7d_attack_count_top_entry(self, client, stats_data):
        """enterprise-attack object A should have count=2 in the 7-day period."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_7_days", "enterprise-attack")
        top = category["results"][0]
        assert top["stix_id"] == "attack-pattern--aaaaaaaa-0000-0000-0000-000000000001"
        assert top["count"] == 2

    def test_7d_attack_ordering(self, client, stats_data):
        """Results within a category are ordered by count descending."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_7_days", "enterprise-attack")
        counts = [result["count"] for result in category["results"]]
        assert counts == sorted(counts, reverse=True)

    def test_30d_attack_count_top_entry(self, client, stats_data):
        """enterprise-attack object A should have count=3 in the 30-day period."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_30_days", "enterprise-attack")
        top = category["results"][0]
        assert top["stix_id"] == "attack-pattern--aaaaaaaa-0000-0000-0000-000000000001"
        assert top["count"] == 3

    def test_7d_cve_count(self, client, stats_data):
        """CVE object should appear once in the 7-day window."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_7_days", "cve")
        assert len(category["results"]) == 1
        assert category["results"][0]["count"] == 1

    def test_sector_absent_from_7d(self, client, stats_data):
        """Sector object modified 20 days ago should not appear in the 7-day window."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_7_days", "sector")
        assert category["results"] == []

    def test_sector_present_in_30d(self, client, stats_data):
        """Sector object modified 20 days ago should appear in the 30-day window."""
        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_30_days", "sector")
        assert len(category["results"]) == 1
        assert category["results"][0]["stix_id"] == "identity--dddddddd-0000-0000-0000-000000000004"

    def test_cwe_absent_from_both_periods(self, client, stats_data):
        """CWE object modified 40 days ago should not appear in either window."""
        data = client.get(STATISTICS_URL).json()
        for period in ("last_7_days", "last_30_days"):
            category = self._get_category(data, period, "cwe")
            assert category["results"] == [], f"Expected no CWE results in {period}"

    def test_max_10_results_per_category(self, client, stats_data, stixifier_profile, identity):
        """Top-10 cap: a category with more than 10 distinct objects returns at most 10."""
        now = timezone.now()

        for i in range(12):
            file_obj = _make_file(
                stixifier_profile,
                identity,
                file_id=f"f80eabde-4bd7-4dc9-8f3f-{i:012d}",
                name=f"top10-file-{i}",
                modified_at=now - timedelta(days=1),
            )
            ObjectValue.objects.create(
                stix_id=f"attack-pattern--{i:08d}-0000-0000-0000-000000000099",
                type="attack-pattern",
                knowledgebase="enterprise-attack",
                values={"name": f"Technique {i}"},
                file=file_obj,
                created=now,
                modified=now,
            )

        data = client.get(STATISTICS_URL).json()
        category = self._get_category(data, "last_7_days", "enterprise-attack")
        assert len(category["results"]) <= 10

    def test_knowledgebase_filter(self, client, stats_data):
        """Filtering by knowledgebase returns only that category in the results."""
        response = client.get(STATISTICS_URL + "?knowledgebase=enterprise-attack")
        assert response.status_code == 200
        data = response.json()

        for period_key in ("last_7_days", "last_30_days"):
            categories = data[period_key]["categories"]
            assert len(categories) == 1, f"Expected exactly 1 category in {period_key}"
            assert categories[0]["knowledgebase"] == "enterprise-attack", f"Expected enterprise-attack category in {period_key}"
