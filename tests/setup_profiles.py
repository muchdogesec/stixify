import requests
import uuid

# Base URL
base_url = "http://localhost:8004/api/v1/profiles/"

# UUIDv5 namespace
namespace_uuid = uuid.UUID("e92c648d-03eb-59a5-a318-9a36e6f8057c")

def get_profile_ids():
    print("Sending GET request to retrieve profiles...")
    response = requests.get(base_url)
    if response.status_code == 200:
        print("Successfully retrieved profiles.")
        data = response.json()
        profile_ids = [profile['id'] for profile in data.get('profiles', [])]
        print(f"Found {len(profile_ids)} profiles.")
        return profile_ids
    else:
        print(f"Failed to retrieve profiles. Status code: {response.status_code}")
        return []

def delete_profiles(profile_ids):
    for profile_id in profile_ids:
        delete_url = f"{base_url}{profile_id}/"
        print(f"Sending DELETE request for profile ID: {profile_id}...")
        response = requests.delete(delete_url)
        if response.status_code == 204:
            print(f"Successfully deleted profile with ID: {profile_id}")
        else:
            print(f"Failed to delete profile with ID: {profile_id}. Status code: {response.status_code}")

def create_profiles(profiles):
    for profile in profiles:
        print(f"Sending POST request to create profile: {profile['name']}...")
        response = requests.post(base_url, json=profile)
        if response.status_code == 201:
            print(f"Successfully created profile: {profile['name']}")
        else:
            print(f"Failed to create profile: {profile['name']}. Status code: {response.status_code}")

def check_profiles(profiles):
    for profile in profiles:
        # Generate the UUIDv5 for the profile name
        profile_id = str(uuid.uuid5(namespace_uuid, profile['name']))
        check_url = f"{base_url}{profile_id}/"
        print(f"Sending GET request to check profile with ID: {profile_id}...")
        response = requests.get(check_url)
        if response.status_code == 200:
            print(f"Profile with ID: {profile_id} exists and is correct.")
        else:
            print(f"Failed to find profile with ID: {profile_id}. Status code: {response.status_code}")

if __name__ == "__main__":
    print("Starting profile deletion, creation, and verification script...")

    # Step 1: Get all profile IDs
    profile_ids = get_profile_ids()

    # Step 2: Delete each profile
    if profile_ids:
        delete_profiles(profile_ids)
    else:
        print("No profiles found to delete.")

    # Step 3: Create new profiles
    profiles = [
        # 24debd60-1774-5587-a6ce-e2e24879b7b4
        {
            "name": "Basic threat intel extractions. Standard relationship. Extract text from images.",
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
            "relationship_mode": "standard",
            "extract_text_from_image": True,
            "defang": True,
            "ignore_image_refs": True,
            "ignore_link_refs": True,
            "ai_summary_provider": "openai:gpt-4o",
            "ignore_extraction_boundary": False,
            "ignore_embedded_relationships": False,
            "ignore_embedded_relationships_sro": False,
            "ignore_embedded_relationships_smo": False,
            "ai_content_check_provider": "openai:gpt-4o",
            "ai_create_attack_flow": False
        },
        # 2919ca71-e60c-5aad-81f7-8cf561645d03
        {
            "name": "Basic threat intel extractions. AI relationship. Extract text from images.",
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
            "extract_text_from_image": True,
            "defang": True,
            "ignore_image_refs": True,
            "ignore_link_refs": True,
            "ai_summary_provider": "openai:gpt-4o",
            "ignore_extraction_boundary": False,
            "ignore_embedded_relationships": False,
            "ignore_embedded_relationships_sro": False,
            "ignore_embedded_relationships_smo": False,
            "ai_content_check_provider": "openai:gpt-4o",
            "ai_create_attack_flow": True
        },
        # 42976b41-6070-5fc3-a87f-ee81c38d26ef
        {
            "name": "External lookups. Standard relationship. Extract text from images.",
            "extractions": [
                "pattern_cryptocurrency_btc_wallet",
                "pattern_cryptocurrency_btc_transaction",
                "pattern_cve_id",
                "pattern_cpe_uri",
                "pattern_bank_card_mastercard",
                "pattern_bank_card_visa",
                "pattern_bank_card_amex",
                "pattern_bank_card_union_pay",
                "pattern_bank_card_diners",
                "pattern_bank_card_jcb",
                "pattern_bank_card_discover",
                "lookup_mitre_attack_enterprise_id",
                "lookup_mitre_attack_mobile_id",
                "lookup_mitre_attack_ics_id",
                "lookup_mitre_capec_id",
                "lookup_mitre_cwe_id",
                "lookup_mitre_atlas_id",
                "lookup_country_alpha2"
            ],
            "relationship_mode": "standard",
            "extract_text_from_image": True,
            "defang": True,
            "ignore_image_refs": True,
            "ignore_link_refs": True,
            "ai_summary_provider": "openai:gpt-4o",
            "ignore_extraction_boundary": False,
            "ignore_embedded_relationships": False,
            "ignore_embedded_relationships_sro": False,
            "ignore_embedded_relationships_smo": False,
            "ai_content_check_provider": "openai:gpt-4o",
            "ai_create_attack_flow": False
        },
        # 4140d4d8-7824-51bc-b10a-3ba1465c8de3
        {
            "name": "AI extractions. AI relationship. Extract text from images.",
            "extractions": [
                "ai_mitre_attack_enterprise",
                "ai_mitre_attack_mobile",
                "ai_mitre_attack_ics",
                "ai_mitre_capec",
                "ai_mitre_cwe"
            ],
            "ai_settings_extractions": [
                "openai:gpt-4o",
                "anthropic:claude-3-5-sonnet-latest",
                "gemini:models/gemini-1.5-pro-latest"
            ],
            "relationship_mode": "ai",
            "ai_settings_relationships": "openai:gpt-4o",
            "extract_text_from_image": True,
            "defang": True,
            "ignore_image_refs": True,
            "ignore_link_refs": True,
            "ai_summary_provider": "openai:gpt-4o",
            "ignore_extraction_boundary": False,
            "ignore_embedded_relationships": False,
            "ignore_embedded_relationships_sro": False,
            "ignore_embedded_relationships_smo": False,
            "ai_content_check_provider": "openai:gpt-4o",
            "ai_create_attack_flow": True
        }
    ]

    create_profiles(profiles)

    # Step 4: Check if profiles were created correctly
    check_profiles(profiles)

    print("Profile deletion, creation, and verification script completed.")
