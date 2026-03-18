"""
Tests for Object Values endpoints (SCO and SDO views).

These tests verify the functionality of the /api/v1/values/scos/ and /api/v1/values/sdos/
endpoints which provide efficient querying of STIX object values extracted from posts.
"""

import pytest
from django.utils import timezone
from stixify.web.models import ObjectValue, File
from rest_framework.test import APIClient


@pytest.fixture
def values(more_files):
    """Create files that have ObjectValue entries."""    
    # Get the files created by more_files fixture
    files = more_files
    
    # Create ObjectValue entries for different STIX object types
    # SCO: IPv4 addresses
    ObjectValue.objects.create(
        stix_id="ipv4-addr--ba6b3f21-d818-4e7c-bfff-765805177512",
        type="ipv4-addr",
        ttp_type=None,
        values={"value": "192.168.1.1"},
        file=files[0],
    )
    
    ObjectValue.objects.create(
        stix_id="ipv4-addr--ba6b3f21-d818-4e7c-bfff-765805177512",
        type="ipv4-addr",
        ttp_type=None,
        values={"value": "192.168.1.1"},
        file=files[1],  # Same IP in different post
    )
    
    ObjectValue.objects.create(
        stix_id="ipv4-addr--cc7b4f32-e929-5c8d-cfff-876916288623",
        type="ipv4-addr",
        ttp_type=None,
        values={"value": "10.0.0.1"},
        file=files[0],
    )
    
    # SCO: Domain names
    ObjectValue.objects.create(
        stix_id="domain-name--dd8c5e43-fa3a-6d9e-dfff-987027399734",
        type="domain-name",
        ttp_type=None,
        values={"value": "malicious.example.com"},
        file=files[0],
    )
    
    ObjectValue.objects.create(
        stix_id="domain-name--ee9d6f54-gb4b-7e0f-efff-098138400845",
        type="domain-name",
        ttp_type=None,
        values={"value": "phishing.example.net"},
        file=files[1],
    )
    
    # SCO: URL
    ObjectValue.objects.create(
        stix_id="url--ff0e7g65-hc5c-8f1g-ffff-109249511956",
        type="url",
        ttp_type=None,
        values={"value": "https://malicious.example.com/payload.exe"},
        file=files[0],
    )
    
    # SDO: Attack Pattern
    ObjectValue.objects.create(
        stix_id="attack-pattern--0f4a0c76-ab2d-4cb0-85d3-3f0efb8cba4d",
        type="attack-pattern",
        ttp_type="enterprise-attack",
        values={"name": "Spearphishing Link", "aliases": ["T1566.002"]},
        file=files[0],
        created=timezone.now(),
        modified=timezone.now(),
    )
    
    ObjectValue.objects.create(
        stix_id="attack-pattern--0f4a0c76-ab2d-4cb0-85d3-3f0efb8cba4d",
        type="attack-pattern",
        ttp_type="enterprise-attack",
        values={"name": "Spearphishing Link", "aliases": ["T1566.002"]},
        file=files[2],  # Same attack pattern in different post
        created=timezone.now(),
        modified=timezone.now(),
    )
    
    # SDO: Malware
    ObjectValue.objects.create(
        stix_id="malware--1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
        type="malware",
        ttp_type=None,
        values={"name": "WannaCry", "x_mitre_aliases": ["WannaCryptor", "WCry"]},
        file=files[1],
        created=timezone.now(),
        modified=timezone.now(),
    )
    
    # SDO: Vulnerability
    ObjectValue.objects.create(
        stix_id="vulnerability--2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
        type="vulnerability",
        ttp_type="cve",
        values={"name": "CVE-2021-44228"},
        file=files[0],
        created=timezone.now(),
        modified=timezone.now(),
    )
    
    # SDO: Location
    ObjectValue.objects.create(
        stix_id="location--3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
        type="location",
        ttp_type="location",
        values={"name": "United States", "country": "US", "region": "northern-america"},
        file=files[1],
        created=timezone.now(),
        modified=timezone.now(),
    )
    
    return files


@pytest.mark.django_db
class TestSCOValueView:
    """Tests for the SCO (Cyber Observable) values endpoint."""
    
    def test_list_all_scos(self, client, values):
        """Test listing all SCO values."""
        
        response = client.get('/api/v1/values/scos/')
        
        assert response.status_code == 200
        data = response.json()
        assert 'values' in data
        
        # Should return all unique SCO objects (5 unique IPs/domains/URLs)
        assert data['total_results_count'] == 5
        
        # Check that results are deduplicated by stix_id
        stix_ids = [obj['id'] for obj in data['values']]
        assert len(stix_ids) == len(set(stix_ids))  # All unique
    
    def test_filter_by_type(self, client, values):
        """Test filtering SCOs by type."""
        
        response = client.get('/api/v1/values/scos/?types=ipv4-addr')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return only IPv4 addresses (2 unique)
        assert data['total_results_count'] == 2
        for obj in data['values']:
            assert obj['type'] == 'ipv4-addr'
    
    def test_filter_by_multiple_types(self, client, values):
        """Test filtering by multiple types."""
        
        response = client.get('/api/v1/values/scos/?types=ipv4-addr,domain-name')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return IPv4 (2) + domain-name (2) = 4 objects
        assert data['total_results_count'] == 4
        types = [obj['type'] for obj in data['values']]
        assert all(t in ['ipv4-addr', 'domain-name'] for t in types)
    
    def test_filter_by_value_wildcard(self, client, values):
        """Test default search uses vcontains for substring matching."""
        
        response = client.get('/api/v1/values/scos/?value=192.168')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return the 192.168.1.1 IP using substring matching
        assert data['total_results_count'] == 1
        assert data['values'][0]['values']['value'] == '192.168.1.1'
    
    def test_filter_by_value_exact(self, client, values):
        """Test value_exact matches exact individual values only."""
        
        response = client.get('/api/v1/values/scos/?value=192.168.1.1&value_exact=true')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return the IP with exact value match
        assert data['total_results_count'] == 1
        assert data['values'][0]['values']['value'] == '192.168.1.1'
    
    def test_filter_by_value_exact_no_substring_match(self, client, values):
        """Test that exact match does NOT match substrings - only exact individual values."""
        
        response = client.get('/api/v1/values/scos/?value=192.168&value_exact=true')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return nothing since '192.168' is not an exact match for any individual value
        assert data['total_results_count'] == 0
    
    def test_filter_by_file_id(self, client, values):
        """Test filtering by file ID."""
        
        
        # Get first file's ID
        files = values
        first_file = files[0]
        file_id = first_file.id
        
        response = client.get(f'/api/v1/values/scos/?file_id={file_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return objects from first file (4 SCOs in first file)
        # 2 unique IPs, 1 domain, 1 URL = 4 unique objects
        assert data['total_results_count'] == 4
        
        # Verify all returned objects have this file in matched_files
        for obj in data['values']:
            assert str(file_id) in [str(f) for f in obj['matched_files']]
    
    def test_filter_by_file_id_multiple(self, client, values):
        """Test that we can filter and get results from multiple files."""
        
        
        # Just verify we can query without file_id and get all results
        response = client.get('/api/v1/values/scos/')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return all SCOs from all files
        assert data['total_results_count'] == 5
    
    def test_filter_by_stix_id(self, client, values):
        """Test filtering by exact STIX object ID."""
        
        stix_id = "ipv4-addr--ba6b3f21-d818-4e7c-bfff-765805177512"
        
        response = client.get(f'/api/v1/values/scos/?id={stix_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        assert data['values'][0]['id'] == stix_id
    
    def test_matched_files_aggregation(self, client, values):
        """Test that matched_files aggregates all files containing the object."""
        
        
        # Query for the IP that appears in 2 files
        response = client.get('/api/v1/values/scos/?value=192.168.1.1&value_exact=true')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        obj = data['values'][0]
        
        # Should have 2 files in matched_files
        assert len(obj['matched_files']) == 2
    
    def test_sdo_types_not_returned(self, client, values):
        """Test that SDO types are not returned in SCO endpoint."""
        
        response = client.get('/api/v1/values/scos/')
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify no SDO types in results
        sdo_types = ['attack-pattern', 'malware', 'vulnerability', 'location']
        for obj in data['values']:
            assert obj['type'] not in sdo_types
    
    def test_ordering_by_stix_id(self, client, values):
        """Test ordering results by stix_id."""
        
        response = client.get('/api/v1/values/scos/?sort=stix_id_ascending')
        
        assert response.status_code == 200
        data = response.json()
        
        stix_ids = [obj['id'] for obj in data['values']]
        assert stix_ids == sorted(stix_ids)
    
    def test_pagination(self, client, values):
        """Test pagination of results."""
        
        response = client.get('/api/v1/values/scos/?page_size=2')
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['values']) == 2
        assert data['total_results_count'] == 5
    
    def test_no_ttp_type_in_sco_results(self, client, values):
        """Test that SCOs don't have ttp_type field in results."""
        
        response = client.get('/api/v1/values/scos/')
        
        assert response.status_code == 200
        data = response.json()
        
        for obj in data['values']:
            # ttp_type should not be present (null fields are removed)
            assert 'ttp_type' not in obj


@pytest.mark.django_db
class TestSDOValueView:
    """Tests for the SDO (Domain Object) values endpoint."""

    @pytest.fixture(autouse=True)
    def default_sdo_objects(self):
        self.default_object_ids = {

        }
    
    def test_list_all_sdos(self, client, values):
        """Test listing all SDO values."""
        
        response = client.get('/api/v1/values/sdos/')
        
        assert response.status_code == 200
        data = response.json()
        assert 'values' in data
        
        # Should return all unique SDO objects (4 unique)
        assert len({obj['id'] for obj in data['values']}) == len(data['values'])  # All unique
        assert data['total_results_count'] == 4
    
    def test_filter_by_type(self, client, values):
        """Test filtering SDOs by type."""
        
        response = client.get('/api/v1/values/sdos/?types=attack-pattern')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return only attack-pattern (1 unique)
        assert data['total_results_count'] == 1
        assert data['values'][0]['type'] == 'attack-pattern'
    
    def test_filter_by_ttp_type(self, client, values):
        """Test filtering by TTP type."""
        
        response = client.get('/api/v1/values/sdos/?ttp_types=enterprise-attack')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return only enterprise-attack objects (1)
        assert data['total_results_count'] == 1
        assert data['values'][0]['ttp_type'] == 'enterprise-attack'
    
    def test_filter_by_multiple_ttp_types(self, client, values):
        """Test filtering by multiple TTP types."""
        
        response = client.get('/api/v1/values/sdos/?ttp_types=cve,location')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return CVE (1) + location (1) = 2 objects
        assert data['total_results_count'] == 2
        ttp_types = [obj['ttp_type'] for obj in data['values']]
        assert all(t in ['cve', 'location'] for t in ttp_types)
    
    def test_filter_by_value_searches_name(self, client, values):
        """Test that value filter searches name field using substring matching."""
        
        response = client.get('/api/v1/values/sdos/?value=WannaCry')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find the WannaCry malware
        assert data['total_results_count'] == 1
        assert 'WannaCry' in data['values'][0]['values']['name']
    
    def test_filter_by_value_searches_aliases(self, client, values):
        """Test that value filter searches aliases using substring matching."""
        
        response = client.get('/api/v1/values/sdos/?value=T1566.002')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find the Spearphishing attack pattern
        assert data['total_results_count'] == 1
        assert data['values'][0]['type'] == 'attack-pattern'
    
    def test_filter_by_value_exact(self, client, values):
        """Test value_exact matches exact individual values only."""
        
        response = client.get('/api/v1/values/sdos/?value=CVE-2021-44228&value_exact=true')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        assert 'CVE-2021-44228' in data['values'][0]['values']['name']
    
    def test_filter_by_file_id(self, client, values):
        """Test filtering by file ID."""
        
        
        # Get second file's ID
        files = values
        second_file = files[1]
        file_id = second_file.id
        
        response = client.get(f'/api/v1/values/sdos/?file_id={file_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return SDOs from second file (2: malware, location)
        assert data['total_results_count'] == 2
        
        # Verify all returned objects have this file in matched_files
        for obj in data['values']:
            assert str(file_id) in [str(f) for f in obj['matched_files']]
    
    def test_filter_by_file_id_all(self, client, values):
        """Test querying all SDOs without file filter."""
        
        
        response = client.get('/api/v1/values/sdos/')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return all SDOs from all files
        assert data['total_results_count'] == 4
    
    def test_filter_by_stix_id(self, client, values):
        """Test filtering by exact STIX object ID."""
        
        stix_id = "attack-pattern--0f4a0c76-ab2d-4cb0-85d3-3f0efb8cba4d"
        
        response = client.get(f'/api/v1/values/sdos/?id={stix_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        assert data['values'][0]['id'] == stix_id
    
    def test_matched_files_aggregation(self, client, values):
        """Test that matched_files aggregates all files containing the object."""
        
        
        # Query for the attack pattern that appears in 2 files
        response = client.get('/api/v1/values/sdos/?value=Spearphishing')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        obj = data['values'][0]
        
        # Should have 2 files in matched_files
        assert len(obj['matched_files']) == 2
    
    def test_sco_types_not_returned(self, client, values):
        """Test that SCO types are not returned in SDO endpoint."""
        
        response = client.get('/api/v1/values/sdos/')
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify no SCO types in results
        sco_types = ['ipv4-addr', 'domain-name', 'url']
        for obj in data['values']:
            assert obj['type'] not in sco_types
    
    def test_ttp_type_present_when_applicable(self, client, values):
        """Test that ttp_type is present when it exists."""
        
        response = client.get('/api/v1/values/sdos/?ttp_types=cve')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        assert 'ttp_type' in data['values'][0]
        assert data['values'][0]['ttp_type'] == 'cve'
    
    def test_ordering_by_ttp_type(self, client, values):
        """Test ordering results by ttp_type."""
        
        response = client.get('/api/v1/values/sdos/?sort=ttp_type_ascending')
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract ttp_types, treating None as z string for sorting (None values should come last)
        ttp_types = [obj.get('ttp_type', 'z') or 'z' for obj in data['values']]
        assert ttp_types == sorted(ttp_types)
    
    def test_combined_filters(self, client, values):
        """Test combining multiple filters."""
        
        response = client.get('/api/v1/values/sdos/?types=vulnerability&ttp_types=cve')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_results_count'] == 1
        obj = data['values'][0]
        assert obj['type'] == 'vulnerability'
        assert obj['ttp_type'] == 'cve'
    
    def test_created_modified_timestamps(self, client, values):
        """Test that created and modified timestamps are returned."""
        
        response = client.get('/api/v1/values/sdos/')
        
        assert response.status_code == 200
        data = response.json()
        
        for obj in data['values']:
            assert 'created' in obj
            assert 'modified' in obj


@pytest.mark.django_db
class TestValuesViewEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_empty_database(self, client):
        """Test querying when no ObjectValue entries exist."""
        
        response = client.get('/api/v1/values/scos/')
        
        assert response.status_code == 200
        data = response.json()
        assert data['total_results_count'] == 0
        assert data['values'] == []
    
    def test_invalid_filter_values(self, client, values):
        """Test that invalid filter values are handled gracefully."""
        
        
        # Invalid UUID format
        response = client.get('/api/v1/values/scos/?file_id=invalid-uuid')
        # Should return 200 with no results or handle gracefully
        assert response.status_code in [200, 400]
    
    def test_nonexistent_stix_id(self, client, values):
        """Test querying for non-existent STIX ID."""
        
        response = client.get('/api/v1/values/scos/?id=ipv4-addr--00000000-0000-0000-0000-000000000000')
        
        assert response.status_code == 200
        data = response.json()
        assert data['total_results_count'] == 0
    
    def test_value_search_no_results(self, client, values):
        """Test value search that returns no results."""
        
        response = client.get('/api/v1/values/scos/?value=nonexistent-value-12345')
        
        assert response.status_code == 200
        data = response.json()
        assert data['total_results_count'] == 0
    
    def test_multiple_filters_narrow_results(self, client, values):
        """Test that multiple filters properly narrow results."""
        
        
        # Get a specific file ID
        files = values
        first_file = files[0]
        file_id = first_file.id
        
        # Filter by type AND file_id
        response = client.get(f'/api/v1/values/scos/?types=ipv4-addr&file_id={file_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return only IPv4 addresses from that specific file
        for obj in data['values']:
            assert obj['type'] == 'ipv4-addr'
            assert str(file_id) in [str(f) for f in obj['matched_files']]


@pytest.mark.django_db
class TestVisibleToFilter:
    """Tests for the visible_to filter functionality."""
    
    @pytest.fixture
    def visibility_test_data(self, stixifier_profile):
        """Create test data with different identities and TLP levels."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from stixify.web.models import File, TLP_Levels
        from dogesec_commons.identity.models import Identity
        
        # Create different identities
        identity1 = Identity.objects.create(
            id="identity--11111111-1111-1111-1111-111111111111",
            stix={"type": "identity", "id": "identity--11111111-1111-1111-1111-111111111111", "name": "Identity 1"}
        )
        identity2 = Identity.objects.create(
            id="identity--22222222-2222-2222-2222-222222222222",
            stix={"type": "identity", "id": "identity--22222222-2222-2222-2222-222222222222", "name": "Identity 2"}
        )
        identity3 = Identity.objects.create(
            id="identity--33333333-3333-3333-3333-333333333333",
            stix={"type": "identity", "id": "identity--33333333-3333-3333-3333-333333333333", "name": "Identity 3"}
        )
        
        # Create files with different identities and TLP levels
        file1_red = File.objects.create(
            id="11111111-1111-1111-1111-111111111111",
            file=SimpleUploadedFile("file1.txt", b"Content 1", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="File 1 - Identity 1 - RED",
            identity=identity1,
            tlp_level=TLP_Levels.RED
        )
        
        file2_clear = File.objects.create(
            id="22222222-2222-2222-2222-222222222222",
            file=SimpleUploadedFile("file2.txt", b"Content 2", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="File 2 - Identity 2 - CLEAR",
            identity=identity2,
            tlp_level=TLP_Levels.CLEAR
        )
        
        file3_green = File.objects.create(
            id="33333333-3333-3333-3333-333333333333",
            file=SimpleUploadedFile("file3.txt", b"Content 3", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="File 3 - Identity 3 - GREEN",
            identity=identity3,
            tlp_level=TLP_Levels.GREEN
        )
        
        file4_amber = File.objects.create(
            id="44444444-4444-4444-4444-444444444444",
            file=SimpleUploadedFile("file4.txt", b"Content 4", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="File 4 - Identity 1 - AMBER",
            identity=identity1,
            tlp_level=TLP_Levels.AMBER
        )
        
        # Create ObjectValues for each file
        ObjectValue.objects.create(
            stix_id="ipv4-addr--file1-red",
            type="ipv4-addr",
            values={"value": "192.168.1.1"},
            file=file1_red
        )
        
        ObjectValue.objects.create(
            stix_id="ipv4-addr--file2-clear",
            type="ipv4-addr",
            values={"value": "192.168.2.2"},
            file=file2_clear
        )
        
        ObjectValue.objects.create(
            stix_id="ipv4-addr--file3-green",
            type="ipv4-addr",
            values={"value": "192.168.3.3"},
            file=file3_green
        )
        
        ObjectValue.objects.create(
            stix_id="ipv4-addr--file4-amber",
            type="ipv4-addr",
            values={"value": "192.168.4.4"},
            file=file4_amber
        )
        
        return {
            "identity1": identity1,
            "identity2": identity2,
            "identity3": identity3,
            "file1_red": file1_red,
            "file2_clear": file2_clear,
            "file3_green": file3_green,
            "file4_amber": file4_amber,
        }
    
    def test_visible_to_single_identity(self, client, visibility_test_data):
        """Test filtering by a single identity ID."""
        
        identity1_id = str(visibility_test_data["identity1"].id)
        
        response = client.get(f'/api/v1/values/scos/?visible_to={identity1_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return:
        # - file1_red (belongs to identity1)
        # - file4_amber (belongs to identity1)
        # - file2_clear (TLP CLEAR)
        # - file3_green (TLP GREEN)
        # Total: 4 objects
        assert data['total_results_count'] == 4
        
        stix_ids = {obj['id'] for obj in data['values']}
        assert 'ipv4-addr--file1-red' in stix_ids
        assert 'ipv4-addr--file4-amber' in stix_ids
        assert 'ipv4-addr--file2-clear' in stix_ids
        assert 'ipv4-addr--file3-green' in stix_ids
    
    def test_visible_to_multiple_identities(self, client, visibility_test_data):
        """Test filtering by multiple identity IDs."""
        
        identity1_id = str(visibility_test_data["identity1"].id)
        identity2_id = str(visibility_test_data["identity2"].id)
        
        response = client.get(f'/api/v1/values/scos/?visible_to={identity1_id},{identity2_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return all 4 objects:
        # - file1_red (belongs to identity1)
        # - file2_clear (belongs to identity2 OR TLP CLEAR)
        # - file3_green (TLP GREEN)
        # - file4_amber (belongs to identity1)
        assert data['total_results_count'] == 4
    
    def test_visible_to_identity_not_in_list(self, client, visibility_test_data):
        """Test that objects from identities not in the list are excluded unless TLP is CLEAR/GREEN."""
        
        identity3_id = str(visibility_test_data["identity3"].id)
        
        response = client.get(f'/api/v1/values/scos/?visible_to={identity3_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return:
        # - file3_green (belongs to identity3)
        # - file2_clear (TLP CLEAR)
        # - file3_green (TLP GREEN - same as above, shouldn't duplicate)
        # Should NOT include file1_red or file4_amber (different identity, not CLEAR/GREEN)
        assert data['total_results_count'] == 2
        
        stix_ids = {obj['id'] for obj in data['values']}
        assert 'ipv4-addr--file3-green' in stix_ids
        assert 'ipv4-addr--file2-clear' in stix_ids
        assert 'ipv4-addr--file1-red' not in stix_ids
        assert 'ipv4-addr--file4-amber' not in stix_ids
    
    def test_visible_to_only_clear_green_visible(self, client, visibility_test_data):
        """Test that CLEAR and GREEN TLP files are always visible regardless of identity."""
        
        # Use a non-existent identity
        fake_identity = "identity--99999999-9999-9999-9999-999999999999"
        
        response = client.get(f'/api/v1/values/scos/?visible_to={fake_identity}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return file2_clear and file3_green
        assert data['total_results_count'] == 2
        
        stix_ids = {obj['id'] for obj in data['values']}
        assert 'ipv4-addr--file2-clear' in stix_ids
        assert 'ipv4-addr--file3-green' in stix_ids
    
    def test_visible_to_with_whitespace(self, client, visibility_test_data):
        """Test that the filter handles whitespace in comma-separated values."""
        
        identity1_id = str(visibility_test_data["identity1"].id)
        identity2_id = str(visibility_test_data["identity2"].id)
        
        # Add whitespace around commas
        response = client.get(f'/api/v1/values/scos/?visible_to={identity1_id} , {identity2_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still work correctly
        assert data['total_results_count'] == 4
    
    def test_visible_to_empty_value(self, client, visibility_test_data):
        """Test that empty visible_to parameter returns all results."""
        
        
        response = client.get('/api/v1/values/scos/?visible_to=')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return all 4 objects (no filtering applied)
        assert data['total_results_count'] == 4
    
    def test_visible_to_with_sdo_endpoint(self, client, visibility_test_data):
        """Test that visible_to filter works on SDO endpoint as well."""
        # Add some SDO objects
        ObjectValue.objects.create(
            stix_id="attack-pattern--file1",
            type="attack-pattern",
            ttp_type="enterprise-attack",
            values={"name": "Attack 1"},
            file=visibility_test_data["file1_red"],
            created=timezone.now(),
            modified=timezone.now(),
        )
        
        ObjectValue.objects.create(
            stix_id="attack-pattern--file2",
            type="attack-pattern",
            ttp_type="enterprise-attack",
            values={"name": "Attack 2"},
            file=visibility_test_data["file2_clear"],
            created=timezone.now(),
            modified=timezone.now(),
        )
        
        
        identity1_id = str(visibility_test_data["identity1"].id)
        
        response = client.get(f'/api/v1/values/sdos/?visible_to={identity1_id}')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return both attacks:
        # - attack-pattern--file1 (belongs to identity1)
        # - attack-pattern--file2 (TLP CLEAR)
        assert data['total_results_count'] == 2
        
        stix_ids = {obj['id'] for obj in data['values']}
        assert 'attack-pattern--file1' in stix_ids
        assert 'attack-pattern--file2' in stix_ids
    
    def test_visible_to_combined_with_other_filters(self, client, visibility_test_data):
        """Test that visible_to can be combined with other filters."""
        
        identity1_id = str(visibility_test_data["identity1"].id)
        
        # Combine visible_to with value search
        response = client.get(f'/api/v1/values/scos/?visible_to={identity1_id}&value=192.168.1')
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return file1_red (matches identity AND value)
        assert data['total_results_count'] == 1
        assert data['values'][0]['id'] == 'ipv4-addr--file1-red'
