## Test pdf

`c800d962-a205-534f-8f4e-e9e8ed772349`

```json
    {
        "identity_id": "identity--1cdc8321-5e67-42de-b2bf-c9505a891492",
        "name": "Test PDF",
        "extractions": [
            "pattern_ipv4_address_only",
            "pattern_ipv6_address_only",
            "pattern_domain_name_only",
            "pattern_url",
            "pattern_file_name",
            "pattern_file_hash_md5",
            "pattern_file_hash_sha_1",
            "pattern_file_hash_sha_256",
            "pattern_file_hash_sha_512",
            "pattern_email_address",
            "pattern_mac_address"
        ],
        "relationship_mode": "ai",
        "ai_settings_relationships": "openai:gpt-4o",
        "extract_text_from_image": false,
        "defang": true,
        "ignore_image_refs": true,
        "ignore_link_refs": true,
        "ignore_extraction_boundary": false,
        "ignore_embedded_relationships": false,
        "ignore_embedded_relationships_sro": true,
        "ignore_embedded_relationships_smo": true,
        "ai_content_check_provider": "openai:gpt-4o",
        "ai_extract_if_no_incidence": true,
        "ai_create_attack_flow":false,
        "ai_create_attack_navigator_layer": false,
        "generate_pdf": true
    }
```

## Pattern AI rel

`942cb852-617f-5b5c-af5f-48040ef80914`

```json
    {
        "identity_id": "identity--1cdc8321-5e67-42de-b2bf-c9505a891492",
        "name": "Pattern with AI relationships",
        "extractions": [
            "pattern_ipv4_address_only",
            "pattern_ipv4_address_port",
            "pattern_ipv4_address_cidr",
            "pattern_ipv6_address_only",
            "pattern_ipv6_address_port",
            "pattern_ipv6_address_cidr",
            "pattern_domain_name_only",
            "pattern_domain_name_subdomain",
            "pattern_url",
            "pattern_url_file",
            "pattern_host_name",
            "pattern_url_path",
            "pattern_host_name",
            "pattern_host_name_subdomain",
            "pattern_host_name_url",
            "pattern_host_name_file",
            "pattern_host_name_path",
            "pattern_file_name",
            "pattern_directory_windows",
            "pattern_directory_windows_with_file",
            "pattern_directory_unix",
            "pattern_directory_unix_file",
            "pattern_file_hash_md5",
            "pattern_file_hash_sha_1",
            "pattern_file_hash_sha_256",
            "pattern_file_hash_sha_512",
            "pattern_email_address",
            "pattern_mac_address",
            "pattern_windows_registry_key",
            "pattern_user_agent",
            "pattern_autonomous_system_number",
            "pattern_iban_number",
            "pattern_phone_number"
        ],
        "relationship_mode": "ai",
        "ai_settings_relationships": "openai:gpt-4o",
        "extract_text_from_image": false,
        "defang": true,
        "ignore_image_refs": true,
        "ignore_link_refs": true,
        "ignore_extraction_boundary": false,
        "ignore_embedded_relationships": false,
        "ignore_embedded_relationships_sro": true,
        "ignore_embedded_relationships_smo": true,
        "ai_content_check_provider": "openai:gpt-4o",
        "ai_extract_if_no_incidence": true,
        "ai_create_attack_flow": true,
        "ai_create_attack_navigator_layer": true,
        "generate_pdf": true
    }
```




ID = `b03a4828-cca4-5f7e-8e19-fe3f0a04277e`

```json
    {
        "name": "AI 1",
        "extractions": [
            "ai_ipv4_address_only",
            "ai_domain_name_only",
            "ai_url",
            "ai_mitre_attack_enterprise"
        ],
        "ai_settings_extractions": ["openai:gpt-4o"],
        "relationship_mode": "ai",
        "ai_settings_relationships": "openai:gpt-4o",
        "extract_text_from_image": false,
        "defang": true,
        "ignore_image_refs": true,
        "ignore_link_refs": true,
        "ignore_extraction_boundary": false,
        "ignore_embedded_relationships": false,
        "ignore_embedded_relationships_sro": true,
        "ignore_embedded_relationships_smo": true,
        "ai_create_attack_flow": false,
        "ai_content_check_provider": "openai:gpt-4o"
    }
```