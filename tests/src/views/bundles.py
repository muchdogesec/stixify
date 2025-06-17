BUNDLE_1 = {
    "type": "bundle",
    "id": "bundle--52d2146c-798a-440f-942f-6fe039fb8995",
    "objects": [
        {
            "type": "marking-definition",
            "spec_version": "2.1",
            "id": "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
            "created": "2022-10-01T00:00:00.000Z",
            "definition_type": "TLP:CLEAR",
            "extensions": {
                "extension-definition--60a3c5c5-0d10-413e-aab3-9e08dde9e88d": {
                    "extension_type": "property-extension",
                    "tlp_2_0": "clear",
                }
            },
        },
        {
            "type": "marking-definition",
            "spec_version": "2.1",
            "id": "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created_by_ref": "identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5",
            "created": "2020-01-01T00:00:00.000Z",
            "definition_type": "statement",
            "definition": {
                "statement": "This object was created using: https://github.com/muchdogesec/txt2stix"
            },
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--97ba4e8b-04f6-57e8-8f6e-3a0f0a7dc0fb",
            ],
        },
        {
            "type": "identity",
            "spec_version": "2.1",
            "id": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created_by_ref": "identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5",
            "created": "2020-01-01T00:00:00.000Z",
            "modified": "2020-01-01T00:00:00.000Z",
            "name": "txt2stix",
            "description": "https://github.com/muchdogsec/txt2stix",
            "identity_class": "system",
            "sectors": ["technology"],
            "contact_information": "https://www.dogesec.com/contact/",
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--97ba4e8b-04f6-57e8-8f6e-3a0f0a7dc0fb",
            ],
        },
        {
            "type": "report",
            "spec_version": "2.1",
            "id": "report--52d2146c-798a-440f-942f-6fe039fb8995",
            "created_by_ref": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created": "2022-08-11T15:18:11.499288Z",
            "modified": "2022-08-11T15:18:11.499288Z",
            "name": "The original report",
            "description": "aexample.com.ng (13.59.11.21), located in Nigeria is compromised to Gather Victim Host Information",
            "published": "2022-08-11T15:18:11.499288Z",
            "object_refs": [
                "indicator--dd695028-06bc-5a67-8f4c-b572916f925e",
                "domain-name--a9847407-cfa9-58ea-aa81-5ecc25c0a464",
                "relationship--27cbbba6-6b9d-5748-97cc-deaa4dcc2f9a",
                "indicator--34c99f8e-a858-54e7-a457-4852a98f03ab",
                "ipv4-addr--de3da98b-98d0-56a3-af1d-9a740df60c7b",
                "relationship--a582943e-e5cf-598c-b8f9-52037eb06f2c",
            ],
            "labels": [
                "txt2stix:indicator_of_compromise",
                "txt2stix:infostealer",
            ],
            "confidence": 91,
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "52d2146c-798a-440f-942f-6fe039fb8995",
                },
                {
                    "source_name": "txt2stix Report MD5",
                    "description": "64d038286cbe970c3e67fdf234571f0e",
                },
            ],
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        },
        {
            "type": "indicator",
            "spec_version": "2.1",
            "id": "indicator--dd695028-06bc-5a67-8f4c-b572916f925e",
            "created_by_ref": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created": "2022-08-11T15:18:11.499288Z",
            "modified": "2022-08-11T15:18:11.499288Z",
            "name": "Domain: aexample.com.ng",
            "indicator_types": ["unknown"],
            "pattern": "[ domain-name:value = 'aexample.com.ng' ]",
            "pattern_type": "stix",
            "pattern_version": "2.1",
            "valid_from": "2022-08-11T15:18:11.499288Z",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "52d2146c-798a-440f-942f-6fe039fb8995",
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_domain_name_only_1.0.0",
                },
            ],
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        },
        {
            "type": "domain-name",
            "spec_version": "2.1",
            "id": "domain-name--a9847407-cfa9-58ea-aa81-5ecc25c0a464",
            "value": "aexample.com.ng",
        },
        {
            "type": "relationship",
            "spec_version": "2.1",
            "id": "relationship--27cbbba6-6b9d-5748-97cc-deaa4dcc2f9a",
            "created_by_ref": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created": "2022-08-11T15:18:11.499288Z",
            "modified": "2022-08-11T15:18:11.499288Z",
            "relationship_type": "detected-using",
            "description": "aexample.com.ng can be detected in the STIX pattern Domain: aexample.com.ng",
            "source_ref": "domain-name--a9847407-cfa9-58ea-aa81-5ecc25c0a464",
            "target_ref": "indicator--dd695028-06bc-5a67-8f4c-b572916f925e",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "52d2146c-798a-440f-942f-6fe039fb8995",
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_domain_name_only_1.0.0",
                },
            ],
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        },
        {
            "type": "indicator",
            "spec_version": "2.1",
            "id": "indicator--34c99f8e-a858-54e7-a457-4852a98f03ab",
            "created_by_ref": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created": "2022-08-11T15:18:11.499288Z",
            "modified": "2022-08-11T15:18:11.499288Z",
            "name": "ipv4: 13.59.11.21",
            "indicator_types": ["unknown"],
            "pattern": "[ ipv4-addr:value = '13.59.11.21' ]",
            "pattern_type": "stix",
            "pattern_version": "2.1",
            "valid_from": "2022-08-11T15:18:11.499288Z",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "52d2146c-798a-440f-942f-6fe039fb8995",
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_ipv4_address_only_1.0.0",
                },
            ],
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        },
        {
            "type": "ipv4-addr",
            "spec_version": "2.1",
            "id": "ipv4-addr--de3da98b-98d0-56a3-af1d-9a740df60c7b",
            "value": "13.59.11.21",
        },
        {
            "type": "relationship",
            "spec_version": "2.1",
            "id": "relationship--a582943e-e5cf-598c-b8f9-52037eb06f2c",
            "created_by_ref": "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created": "2022-08-11T15:18:11.499288Z",
            "modified": "2022-08-11T15:18:11.499288Z",
            "relationship_type": "detected-using",
            "description": "13.59.11.21 can be detected in the STIX pattern ipv4: 13.59.11.21",
            "source_ref": "ipv4-addr--de3da98b-98d0-56a3-af1d-9a740df60c7b",
            "target_ref": "indicator--34c99f8e-a858-54e7-a457-4852a98f03ab",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "52d2146c-798a-440f-942f-6fe039fb8995",
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_ipv4_address_only_1.0.0",
                },
            ],
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            ],
        },
    ],
}


BUNDLE_2 = {
    "type": "bundle",
    "id": "bundle--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
    "objects": [
        {
            "type": "marking-definition",
            "spec_version": "2.1",
            "id": "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
            "created": "2022-10-01T00:00:00.000Z",
            "definition_type": "TLP:AMBER",
            "extensions": {
                "extension-definition--60a3c5c5-0d10-413e-aab3-9e08dde9e88d": {
                    "extension_type": "property-extension",
                    "tlp_2_0": "amber"
                }
            }
        },
        {
            "type": "marking-definition",
            "spec_version": "2.1",
            "id": "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
            "created_by_ref": "identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5",
            "created": "2020-01-01T00:00:00.000Z",
            "definition_type": "statement",
            "definition": {
                "statement": "This object was created using: https://github.com/muchdogesec/txt2stix"
            },
            "object_marking_refs": [
                "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
                "marking-definition--97ba4e8b-04f6-57e8-8f6e-3a0f0a7dc0fb"
            ]
        },
        {
            "type": "identity",
            "id": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T14:26:48.932Z",
            "modified": "2025-06-17T14:26:48.932Z",
            "name": "dummy identity",
            "identity_class": "individual"
        },
        {
            "type": "report",
            "spec_version": "2.1",
            "id": "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab",
            "created_by_ref": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T15:26:48.932465Z",
            "modified": "2025-06-17T15:26:48.932465Z",
            "name": "This is another report",
            "description": "T1120 is followed by T1123. \nTarget is located in Nigeria and the red team of ak99za hacked the hospital using CVE-2025-19123\nncsc.gov.uk",
            "published": "2025-06-17T15:26:48.932465Z",
            "object_refs": [
                "indicator--21c8753d-a681-5159-949d-72d6b1fefb89",
                "indicator--7a95323c-c59e-5e10-8edc-a24f5001b58e",
                "domain-name--791a1b67-147a-568f-b515-b4184f3d48f3",
                "relationship--81a3e593-b36f-5da8-bc98-8e8b92e1730b"
            ],
            "labels": [
                "txt2stix:vulnerability",
                "txt2stix:exploit",
                "txt2stix:ttp",
                "txt2stix:cyber_crime"
            ],
            "confidence": 17,
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "ed758a1b-34fe-4fca-8178-0c30d93a03ab"
                },
                {
                    "source_name": "txt2stix Report MD5",
                    "description": "392b9b9bec554f8564eea2b166b72bbe"
                }
            ],
            "object_marking_refs": [
                "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"
            ]
        },
        {
            "type": "indicator",
            "spec_version": "2.1",
            "id": "indicator--21c8753d-a681-5159-949d-72d6b1fefb89",
            "created_by_ref": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T15:26:48.932465Z",
            "modified": "2025-06-17T15:26:48.932465Z",
            "name": "CVE-2025-19123",
            "indicator_types": [
                "unknown"
            ],
            "pattern": "[ vulmatch-cve-id:value = 'CVE-2025-19123' ]",
            "pattern_type": "stix",
            "pattern_version": "2.1",
            "valid_from": "2025-06-17T15:26:48.932465Z",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "ed758a1b-34fe-4fca-8178-0c30d93a03ab"
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_cve_id_1.0.0"
                }
            ],
            "object_marking_refs": [
                "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"
            ]
        },
        {
            "type": "indicator",
            "spec_version": "2.1",
            "id": "indicator--7a95323c-c59e-5e10-8edc-a24f5001b58e",
            "created_by_ref": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T15:26:48.932465Z",
            "modified": "2025-06-17T15:26:48.932465Z",
            "name": "Domain: ncsc.gov.uk",
            "indicator_types": [
                "unknown"
            ],
            "pattern": "[ domain-name:value = 'ncsc.gov.uk' ]",
            "pattern_type": "stix",
            "pattern_version": "2.1",
            "valid_from": "2025-06-17T15:26:48.932465Z",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "ed758a1b-34fe-4fca-8178-0c30d93a03ab"
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_domain_name_only_1.0.0"
                }
            ],
            "object_marking_refs": [
                "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"
            ]
        },
        {
            "type": "domain-name",
            "spec_version": "2.1",
            "id": "domain-name--791a1b67-147a-568f-b515-b4184f3d48f3",
            "value": "ncsc.gov.uk"
        },
        {
            "type": "relationship",
            "spec_version": "2.1",
            "id": "relationship--81a3e593-b36f-5da8-bc98-8e8b92e1730b",
            "created_by_ref": "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30",
            "created": "2025-06-17T15:26:48.932465Z",
            "modified": "2025-06-17T15:26:48.932465Z",
            "relationship_type": "detected-using",
            "description": "ncsc.gov.uk can be detected in the STIX pattern Domain: ncsc.gov.uk",
            "source_ref": "domain-name--791a1b67-147a-568f-b515-b4184f3d48f3",
            "target_ref": "indicator--7a95323c-c59e-5e10-8edc-a24f5001b58e",
            "external_references": [
                {
                    "source_name": "txt2stix_report_id",
                    "external_id": "ed758a1b-34fe-4fca-8178-0c30d93a03ab"
                },
                {
                    "source_name": "txt2stix_extraction_type",
                    "description": "pattern_domain_name_only_1.0.0"
                }
            ],
            "object_marking_refs": [
                "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
                "marking-definition--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"
            ]
        }
    ]
}