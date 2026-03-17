"""
Tests for the values.py module that extracts metadata from STIX objects.

These tests verify the core functionality of extracting values from different STIX object types,
determining TTP types, and processing objects through the post-upload hook.
"""

import pytest
from datetime import datetime, timezone
from stixify.web.values.values import (
    external_id,
    hashes,
    get_file_values,
    get_location_values,
    get_values,
    get_ttp_type,
    extract_object_metadata,
    process_uploaded_objects_hook,
    sco_value_map,
    sdo_value_map,
)
from stixify.web.models import ObjectValue, File
from unittest.mock import Mock, patch
import logging


class TestHelperFunctions:
    """Tests for helper functions that extract specific data from STIX objects."""
    
    def test_external_id_extracts_first_id(self):
        """Test that external_id extracts the first external_id from external_references."""
        obj = {
            "external_references": [
                {"source_name": "cve", "external_id": "CVE-2021-44228"},
                {"source_name": "nist", "external_id": "NVD-2021-44228"},
            ]
        }
        result = external_id(obj)
        assert result == ["CVE-2021-44228"]
    
    def test_external_id_returns_empty_when_none(self):
        """Test that external_id returns empty list when no external_id present."""
        obj = {"external_references": [{"source_name": "cve", "url": "http://example.com"}]}
        result = external_id(obj)
        assert result == []
    
    def test_external_id_handles_missing_references(self):
        """Test that external_id handles missing external_references."""
        obj = {}
        result = external_id(obj)
        assert result == []
    
    def test_hashes_extracts_hash_dict(self):
        """Test that hashes extracts the hashes dictionary."""
        obj = {"hashes": {"MD5": "abc123", "SHA-256": "def456"}}
        result = hashes(obj)
        assert result == {"MD5": "abc123", "SHA-256": "def456"}
    
    def test_hashes_returns_empty_when_missing(self):
        """Test that hashes returns empty dict when not present."""
        obj = {}
        result = hashes(obj)
        assert result == {}
    
    def test_get_file_values_extracts_name_and_hashes(self):
        """Test that get_file_values extracts file name and normalizes hashes."""
        obj = {
            "name": "malware.exe",
            "hashes": {
                "MD5": "abc123",
                "SHA-256": "def456",
                "SHA-1": "ghi789"
            }
        }
        result = get_file_values(obj)
        assert result == {
            "name": "malware.exe",
            "md5": "abc123",
            "sha256": "def456",
            "sha1": "ghi789"
        }
    
    def test_get_file_values_handles_missing_fields(self):
        """Test that get_file_values handles missing name or hashes."""
        obj = {"name": "test.txt"}
        result = get_file_values(obj)
        assert result == {"name": "test.txt"}
        
        obj = {"hashes": {"MD5": "abc"}}
        result = get_file_values(obj)
        assert result == {"md5": "abc"}
    
    def test_get_location_values_extracts_name_and_region(self):
        """Test that get_location_values extracts name and region."""
        obj = {
            "name": "United States",
            "region": "northern-america",
            "latitude": 37.0902
        }
        result = get_location_values(obj)
        assert result == {
            "name": "United States",
            "region": "northern-america"
        }
    
    def test_get_location_values_extracts_from_external_refs(self):
        """Test that get_location_values extracts type and alpha-3 codes."""
        obj = {
            "name": "United States",
            "external_references": [
                {"source_name": "type", "external_id": "country"},
                {"source_name": "alpha-3", "external_id": "USA"}
            ]
        }
        result = get_location_values(obj)
        assert result == {
            "name": "United States",
            "type": "country",
            "alpha-3": "USA"
        }
    
    def test_get_values_with_list(self):
        """Test that get_values works with a list of keys."""
        obj = {"name": "Test", "version": "1.0", "description": "A test object"}
        keys = ["name", "version"]
        result = get_values(obj, keys)
        assert result == {"name": "Test", "version": "1.0"}
    
    def test_get_values_with_dict(self):
        """Test that get_values works with a dict mapping."""
        obj = {"name": "Test", "version": "1.0"}
        keys = {"name": "title", "version": "ver"}
        result = get_values(obj, keys)
        assert result == {"name": "Test", "version": "1.0"}
    
    def test_get_values_with_callable(self):
        """Test that get_values works with a callable function."""
        obj = {"name": "Test", "value": "123"}
        def custom_extractor(o):
            return {"custom": o["name"] + "_" + o["value"]}
        result = get_values(obj, custom_extractor)
        assert result == {"custom": "Test_123"}
    
    def test_get_values_skips_missing_keys(self):
        """Test that get_values skips keys not present in object."""
        obj = {"name": "Test"}
        keys = ["name", "version", "description"]
        result = get_values(obj, keys)
        assert result == {"name": "Test"}
    
    def test_get_values_raises_error_for_invalid_type(self):
        """Test that get_values raises ValueError for invalid key type."""
        obj = {"name": "Test"}
        with pytest.raises(ValueError, match="value_keys must be a list, a dictionary, or a callable"):
            get_values(obj, 123)


class TestGetTTPType:
    """Tests for the get_ttp_type function that determines TTP classification."""
    
    def test_vulnerability_returns_cve(self):
        """Test that vulnerability objects return 'cve' as ttp_type."""
        obj = {
            "type": "vulnerability",
            "external_references": [{"source_name": "cve", "external_id": "CVE-2021-44228"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "cve"
        assert extra == {"ttp_id": "CVE-2021-44228"}
    
    def test_weakness_returns_cwe(self):
        """Test that weakness objects return 'cwe' as ttp_type."""
        obj = {
            "type": "weakness",
            "external_references": [{"source_name": "cwe", "external_id": "CWE-79"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "cwe"
        assert extra == {"ttp_id": "CWE-79"}
    
    def test_location_returns_location(self):
        """Test that location objects return 'location' as ttp_type."""
        obj = {"type": "location", "name": "United States"}
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "location"
        assert extra == {}
    
    def test_enterprise_attack_from_x_mitre_domains(self):
        """Test that enterprise-attack is detected from x_mitre_domains."""
        obj = {
            "type": "attack-pattern",
            "x_mitre_domains": ["enterprise-attack"],
            "external_references": [{"source_name": "mitre-attack", "external_id": "T1566.002"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "enterprise-attack"
        assert extra == {"ttp_id": "T1566.002"}
    
    def test_mobile_attack_from_x_mitre_domains(self):
        """Test that mobile-attack is detected from x_mitre_domains."""
        obj = {
            "type": "attack-pattern",
            "x_mitre_domains": ["mobile-attack"]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "mobile-attack"
    
    def test_ics_attack_from_x_mitre_domains(self):
        """Test that ics-attack is detected from x_mitre_domains."""
        obj = {
            "type": "attack-pattern",
            "x_mitre_domains": ["ics-attack"]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "ics-attack"
    
    def test_capec_from_external_references(self):
        """Test that CAPEC is detected from external_references."""
        obj = {
            "type": "attack-pattern",
            "external_references": [{"source_name": "capec", "external_id": "CAPEC-63"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "capec"
        assert extra == {"ttp_id": "CAPEC-63"}
    
    def test_atlas_from_external_references(self):
        """Test that ATLAS is detected from external_references."""
        obj = {
            "type": "attack-pattern",
            "external_references": [{"source_name": "mitre-atlas", "external_id": "AML.T0001"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "atlas"
        assert extra == {"ttp_id": "AML.T0001"}
    
    def test_disarm_from_external_references(self):
        """Test that DISARM is detected from external_references."""
        obj = {
            "type": "attack-pattern",
            "external_references": [{"source_name": "DISARM", "external_id": "T0001"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "disarm"
        assert extra == {"ttp_id": "T0001"}
    
    def test_sector_from_external_references(self):
        """Test that sector is detected from external_references."""
        obj = {
            "type": "identity",
            "external_references": [{"source_name": "sector2stix", "external_id": "financial"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "sector"
        assert extra == {"ttp_id": "financial"}
    
    def test_non_ttp_returns_none(self):
        """Test that non-TTP objects return None."""
        obj = {"type": "indicator", "name": "Malicious IP"}
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type is None
        assert extra == {}
    
    def test_ttp_without_external_id(self):
        """Test TTP type without external_id in references."""
        obj = {
            "type": "vulnerability",
            "external_references": [{"source_name": "cve", "url": "http://example.com"}]
        }
        ttp_type, extra = get_ttp_type(obj)
        assert ttp_type == "cve"
        assert extra == {}

class TestExtractObjectMetadata:
    """Tests for the extract_object_metadata function."""
    
    def test_extract_ipv4_metadata(self):
        """Test extracting metadata from an IPv4 address object."""
        obj = {
            "id": "ipv4-addr--123",
            "type": "ipv4-addr",
            "value": "192.168.1.1",
            "created": "2021-01-01T00:00:00.000Z",
            "modified": "2021-01-01T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "ipv4-addr--123"
        assert result["type"] == "ipv4-addr"
        assert result["ttp_type"] is None
        assert result["values"] == {"value": "192.168.1.1"}
        assert result["created"] == "2021-01-01T00:00:00.000Z"
        assert result["modified"] == "2021-01-01T00:00:00.000Z"
    
    def test_extract_domain_metadata(self):
        """Test extracting metadata from a domain-name object."""
        obj = {
            "id": "domain-name--456",
            "type": "domain-name",
            "value": "malicious.example.com"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "domain-name--456"
        assert result["type"] == "domain-name"
        assert result["values"] == {"value": "malicious.example.com"}
    
    def test_extract_file_metadata_with_hashes(self):
        """Test extracting metadata from a file object with hashes."""
        obj = {
            "id": "file--789",
            "type": "file",
            "name": "malware.exe",
            "hashes": {"MD5": "abc123", "SHA-256": "def456"}
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "file--789"
        assert result["type"] == "file"
        assert result["values"] == {
            "name": "malware.exe",
            "md5": "abc123",
            "sha256": "def456"
        }
    
    def test_extract_attack_pattern_metadata(self):
        """Test extracting metadata from an attack-pattern object."""
        obj = {
            "id": "attack-pattern--abc",
            "type": "attack-pattern",
            "name": "Spearphishing Link",
            "aliases": ["T1566.002"],
            "x_mitre_domains": ["enterprise-attack"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1566.002"}
            ],
            "created": "2020-01-01T00:00:00.000Z",
            "modified": "2020-01-01T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "attack-pattern--abc"
        assert result["type"] == "attack-pattern"
        assert result["ttp_type"] == "enterprise-attack"
        assert result["values"]["name"] == "Spearphishing Link"
        assert result["values"]["aliases"] == "['T1566.002']"
        assert result["values"]["ttp_id"] == "T1566.002"
    
    def test_extract_vulnerability_metadata(self):
        """Test extracting metadata from a vulnerability object."""
        obj = {
            "id": "vulnerability--def",
            "type": "vulnerability",
            "name": "CVE-2021-44228",
            "external_references": [
                {"source_name": "cve", "external_id": "CVE-2021-44228"}
            ],
            "created": "2021-12-10T00:00:00.000Z",
            "modified": "2021-12-10T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "vulnerability--def"
        assert result["type"] == "vulnerability"
        assert result["ttp_type"] == "cve"
        assert result["values"]["name"] == "CVE-2021-44228"
        assert result["values"]["ttp_id"] == "CVE-2021-44228"
    
    def test_extract_malware_metadata(self):
        """Test extracting metadata from a malware object."""
        obj = {
            "id": "malware--ghi",
            "type": "malware",
            "name": "WannaCry",
            "x_mitre_aliases": ["WannaCryptor", "WCry"],
            "created": "2017-05-12T00:00:00.000Z",
            "modified": "2017-05-12T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "malware--ghi"
        assert result["type"] == "malware"
        assert result["values"]["name"] == "WannaCry"
        assert "WannaCryptor" in result["values"]["x_mitre_aliases"]
    
    def test_extract_location_metadata(self):
        """Test extracting metadata from a location object."""
        obj = {
            "id": "location--jkl",
            "type": "location",
            "name": "United States",
            "region": "northern-america",
            "external_references": [
                {"source_name": "alpha-3", "external_id": "USA"}
            ],
            "created": "2020-01-01T00:00:00.000Z",
            "modified": "2020-01-01T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "location--jkl"
        assert result["type"] == "location"
        assert result["ttp_type"] == "location"
        assert result["values"]["name"] == "United States"
        assert result["values"]["region"] == "northern-america"
        assert result["values"]["alpha-3"] == "USA"
    
    def test_extract_object_without_values(self):
        """Test extracting metadata from object type not in value maps."""
        obj = {
            "id": "unknown-type--xyz",
            "type": "unknown-type"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "unknown-type--xyz"
        assert result["type"] == "unknown-type"
        assert result["values"] == {}
    
    def test_extract_indicator_with_pattern(self):
        """Test extracting metadata from an indicator object."""
        obj = {
            "id": "indicator--mno",
            "type": "indicator",
            "name": "Malicious IP Indicator",
            "pattern": "[ipv4-addr:value = '192.168.1.1']",
            "created": "2021-01-01T00:00:00.000Z",
            "modified": "2021-01-01T00:00:00.000Z"
        }
        result = extract_object_metadata(obj)
        assert result["stix_id"] == "indicator--mno"
        assert result["type"] == "indicator"
        assert result["values"]["name"] == "Malicious IP Indicator"
        assert result["values"]["pattern"] == "[ipv4-addr:value = '192.168.1.1']"


@pytest.mark.django_db
class TestProcessUploadedObjectsHook:
    """Tests for the process_uploaded_objects_hook function."""
    
    def test_hook_creates_object_values(self, stixifier_profile, identity):
        """Test that the hook creates ObjectValue records for uploaded objects."""
        # Create a file
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("test.txt", b"Test Content", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="Test File",
            identity=identity,
        )
        
        # Create STIX objects to process
        objects = [
            {
                "id": "ipv4-addr--123",
                "type": "ipv4-addr",
                "value": "192.168.1.1",
                "_stixify_report_id": f"report--{file.id}"
            },
            {
                "id": "domain-name--456",
                "type": "domain-name",
                "value": "malicious.example.com",
                "_stixify_report_id": f"report--{file.id}"
            }
        ]
        
        # Call the hook
        mock_instance = Mock()
        process_uploaded_objects_hook(mock_instance, "test_collection", objects)
        
        # Verify ObjectValue records were created
        assert ObjectValue.objects.count() == 2
        
        ipv4_obj = ObjectValue.objects.get(stix_id="ipv4-addr--123")
        assert ipv4_obj.type == "ipv4-addr"
        assert ipv4_obj.values == {"value": "192.168.1.1"}
        assert str(ipv4_obj.file.id) == str(file.id)
        
        domain_obj = ObjectValue.objects.get(stix_id="domain-name--456")
        assert domain_obj.type == "domain-name"
        assert domain_obj.values == {"value": "malicious.example.com"}
        assert str(domain_obj.file.id) == str(file.id)
    
    def test_hook_skips_objects_without_report_id(self, stixifier_profile, identity, caplog):
        """Test that the hook skips objects without _stixify_report_id."""
        with caplog.at_level(logging.WARNING):
            objects = [
                {
                    "id": "ipv4-addr--123",
                    "type": "ipv4-addr",
                    "value": "192.168.1.1"
                }
            ]
            
            mock_instance = Mock()
            process_uploaded_objects_hook(mock_instance, "test_collection", objects)
            
            # Verify no records were created
            assert ObjectValue.objects.count() == 0
            
            # Verify warning was logged
            assert "does not have a valid _stixify_report_id" in caplog.text
    
    def test_hook_skips_objects_without_values(self, stixifier_profile, identity):
        """Test that the hook skips objects that don't extract any values."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("test.txt", b"Test Content", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="Test File",
            identity=identity,
        )
        
        objects = [
            {
                "id": "unknown-type--123",
                "type": "unknown-type",
                "_stixify_report_id": f"report--{file.id}"
            }
        ]
        
        mock_instance = Mock()
        process_uploaded_objects_hook(mock_instance, "test_collection", objects)
        
        # Verify no records were created
        assert ObjectValue.objects.count() == 0
    
    def test_hook_handles_duplicate_objects(self, stixifier_profile, identity):
        """Test that the hook handles duplicate objects gracefully."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("test.txt", b"Test Content", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="Test File",
            identity=identity,
        )
        
        # Create an existing ObjectValue
        ObjectValue.objects.create(
            stix_id="ipv4-addr--123",
            type="ipv4-addr",
            values={"value": "192.168.1.1"},
            file=file
        )
        
        # Try to create the same object again
        objects = [
            {
                "id": "ipv4-addr--123",
                "type": "ipv4-addr",
                "value": "192.168.1.1",
                "_stixify_report_id": f"report--{file.id}"
            }
        ]
        
        mock_instance = Mock()
        process_uploaded_objects_hook(mock_instance, "test_collection", objects)
        
        # Verify still only one record exists
        assert ObjectValue.objects.count() == 1
    
    def test_hook_processes_mixed_object_types(self, stixifier_profile, identity):
        """Test that the hook correctly processes various STIX object types."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("test.txt", b"Test Content", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="Test File",
            identity=identity,
        )
        
        objects = [
            {
                "id": "ipv4-addr--123",
                "type": "ipv4-addr",
                "value": "10.0.0.1",
                "_stixify_report_id": f"report--{file.id}"
            },
            {
                "id": "attack-pattern--abc",
                "type": "attack-pattern",
                "name": "Phishing",
                "x_mitre_domains": ["enterprise-attack"],
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}],
                "created": "2020-01-01T00:00:00.000Z",
                "modified": "2020-01-01T00:00:00.000Z",
                "_stixify_report_id": f"report--{file.id}"
            },
            {
                "id": "vulnerability--def",
                "type": "vulnerability",
                "name": "CVE-2021-1234",
                "external_references": [{"source_name": "cve", "external_id": "CVE-2021-1234"}],
                "created": "2021-01-01T00:00:00.000Z",
                "modified": "2021-01-01T00:00:00.000Z",
                "_stixify_report_id": f"report--{file.id}"
            }
        ]
        
        mock_instance = Mock()
        process_uploaded_objects_hook(mock_instance, "test_collection", objects)
        
        # Verify all records were created
        assert ObjectValue.objects.count() == 3
        
        # Verify SCO
        ipv4_obj = ObjectValue.objects.get(stix_id="ipv4-addr--123")
        assert ipv4_obj.ttp_type is None
        
        # Verify SDO with TTP type
        attack_obj = ObjectValue.objects.get(stix_id="attack-pattern--abc")
        assert attack_obj.ttp_type == "enterprise-attack"
        assert attack_obj.values["ttp_id"] == "T1566"
        assert attack_obj.created is not None
        
        # Verify vulnerability
        vuln_obj = ObjectValue.objects.get(stix_id="vulnerability--def")
        assert vuln_obj.ttp_type == "cve"
        assert vuln_obj.values["ttp_id"] == "CVE-2021-1234"
    
    def test_hook_logs_processing_info(self, stixifier_profile, identity, caplog):
        """Test that the hook logs appropriate information."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = File.objects.create(
            id="f3848d80-b14d-4aa6-b3a6-94bce54b217e",
            file=SimpleUploadedFile("test.txt", b"Test Content", "text/plain"),
            profile=stixifier_profile,
            mode="txt",
            name="Test File",
            identity=identity,
        )
        
        objects = [
            {
                "id": "ipv4-addr--123",
                "type": "ipv4-addr",
                "value": "192.168.1.1",
                "_stixify_report_id": f"report--{file.id}"
            }
        ]
        
        with caplog.at_level(logging.INFO):
            mock_instance = Mock()
            process_uploaded_objects_hook(mock_instance, "test_collection", objects)
            
            # Verify info logs
            assert "Processing 1 objects for ObjectValue extraction" in caplog.text
            assert "Created" in caplog.text and "ObjectValue records" in caplog.text


class TestValueMaps:
    """Tests to ensure value maps are properly defined."""
    
    def test_sco_value_map_has_common_types(self):
        """Test that SCO value map contains common observable types."""
        expected_types = [
            "ipv4-addr", "ipv6-addr", "domain-name", "url", "file",
            "email-addr", "mac-addr", "autonomous-system"
        ]
        for obj_type in expected_types:
            assert obj_type in sco_value_map, f"{obj_type} should be in sco_value_map"
    
    def test_sdo_value_map_has_common_types(self):
        """Test that SDO value map contains common domain object types."""
        expected_types = [
            "attack-pattern", "malware", "vulnerability", "threat-actor",
            "campaign", "indicator", "location"
        ]
        for obj_type in expected_types:
            assert obj_type in sdo_value_map, f"{obj_type} should be in sdo_value_map"
    
    def test_value_maps_have_correct_structure(self):
        """Test that all entries in value maps have the correct structure."""
        for obj_type, config in sco_value_map.items():
            assert "values" in config, f"{obj_type} should have 'values' key"
            assert isinstance(config["values"], (list, dict)) or callable(config["values"])
        
        for obj_type, config in sdo_value_map.items():
            assert "values" in config, f"{obj_type} should have 'values' key"
            assert isinstance(config["values"], (list, dict)) or callable(config["values"])
