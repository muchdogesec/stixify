import requests
import time
import os

# Base URLs for API endpoints
BASE_URL = "http://127.0.0.1:8004/api/v1/"
FILES_ENDPOINT = f"{BASE_URL}files/"
JOBS_ENDPOINT = f"{BASE_URL}jobs/"
REPORTS_ENDPOINT = f"{BASE_URL}reports/"

# Directory path for files
FILES_DIR = os.path.join(os.path.dirname(__file__), "files")

# Function to delete a report by its ID
def delete_report(report_id):
    delete_url = f"{REPORTS_ENDPOINT}report--{report_id}/"
    response = requests.delete(delete_url)
    print(f"DELETE Request to {delete_url}")
    print("Response Status Code:", response.status_code)
    print("Response Body:", response.text)

    if response.status_code == 204:
        print(f"Report {report_id} deleted successfully.")
    else:
        print(f"Failed to delete report {report_id}: {response.status_code} - {response.text}")

# Helper function to make the file upload request
def upload_file(profile_id, mode, name, tlp_level, confidence, labels, file_path, report_id, ai_summary_provider):
    with open(file_path, 'rb') as file:
        files = {
            'profile_id': (None, profile_id),
            'mode': (None, mode),
            'name': (None, name),
            'tlp_level': (None, tlp_level),
            'confidence': (None, str(confidence)),
            'labels': (None, ','.join(labels)),
            'file': (os.path.basename(file_path), file, 'application/pdf'),
            'report_id': (None, report_id),
            'ai_summary_provider': (None, ai_summary_provider),
        }
        response = requests.post(FILES_ENDPOINT, files=files)
        print(f"POST Request to {FILES_ENDPOINT}")
        print("Request Files:", files)
        print("Response Status Code:", response.status_code)
        print("Response Body:", response.text)  # Print full response text to help debug 400 errors
        response.raise_for_status()
        return response.json().get("id")

# Helper function to poll the job status until it's completed
def poll_job_status(job_id, max_retries=10, interval=30):
    for attempt in range(max_retries):
        response = requests.get(f"{JOBS_ENDPOINT}{job_id}")
        print(f"GET Request to {JOBS_ENDPOINT}{job_id}")
        print("Response Status Code:", response.status_code)
        print("Response Body:", response.json())
        response.raise_for_status()
        
        job_status = response.json()
        state = job_status.get("state")
        print(f"Attempt {attempt + 1}: Job {job_id} state is '{state}'")
        
        if state == "completed":
            print("Job completed successfully.")
            return job_status
        elif state in {"processing_failed", "retrieve_failed"}:
            raise RuntimeError(f"Job {job_id} failed with state: {state}")

        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete in time.")

# Function to run a single test case
def run_single_test(test_case):
    file_path = os.path.join(FILES_DIR, test_case["file_name"])
    job_id = upload_file(
        profile_id=test_case["profile_id"],
        mode=test_case["mode"],
        name=test_case["name"],
        tlp_level=test_case["tlp_level"],
        confidence=test_case["confidence"],
        labels=test_case["labels"],
        file_path=file_path,
        report_id=test_case["report_id"],
        ai_summary_provider=test_case["ai_summary_provider"]
    )
    print(f"File '{test_case['file_name']}' uploaded successfully. Job ID: {job_id}")
    
    # Poll the job status until completed
    job_result = poll_job_status(job_id)
    print(f"Job result for '{test_case['file_name']}':", job_result)

# Main function to run all test cases
def run_all_tests():
    # Define test cases as a list of dictionaries
    test_cases = [
    # PDF
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "pdf",
            "name": "Fanged data good PDF",
            "tlp_level": "clear",
            "confidence": 99,
            "labels": [
                "label1",
                "label2"
            ],
            "file_name": "pdf/fanged_data_good.pdf",
            "report_id": "6cb8665e-3607-4bbe-a9a3-c2a46bd13630",
            "ai_summary_provider": "openai:gpt-4o"
        },
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "pdf",
            "name": "txt2stix all cases pdf",
            "tlp_level": "amber",
            "confidence": 80,
            "labels": [
                "label1"
            ],
            "file_name": "pdf/txt2stix-all-cases.pdf",
            "report_id": "b2869cb5-5270-4543-ac71-601cc8cd2e3b",
            "ai_summary_provider": "openai:gpt-4o"
        },
    # PDF Real
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "pdf",
            "name": "Bitdefender rdstealer",
            "tlp_level": "amber",
            "confidence": 80,
            "labels": [
                "label1"
            ],
            "file_name": "pdf-real/bitdefender-rdstealer.pdf",
            "report_id": "aaec934b-9141-4ff7-958b-3b99a7b24234",
            "ai_summary_provider": "openai:gpt-4o"
        },
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "pdf",
            "name": "Mandiant APT1",
            "tlp_level": "amber",
            "confidence": 80,
            "labels": [
                "label1"
                ],
            "file_name": "pdf-real/mandiant-apt1-report.pdf",
            "report_id": "65ba4fa9-dfff-4597-bcb9-eb749bb84642",
            "ai_summary_provider": "openai:gpt-4o"
        },
    # HTML article
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "html_article",
            "name": "GroupIB 0ktapus",
            "tlp_level": "amber+strict",
            "confidence": 80,
            "labels": [
                "label1"
            ],
            "file_name": "html-real/group-ib-0ktapus.html",
            "report_id": "5795e067-72a4-4953-87ed-f6c56dc6f639",
            "ai_summary_provider": "openai:gpt-4o"
        },
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "html_article",
            "name": "Unit42 Ursa",
            "tlp_level": "red",
            "confidence": 34,
            "labels": [
                "label2"
            ],
            "file_name": "html-real/unit42-Fighting-Ursa-Luring-Targets-With-Car-for-Sale.html",
            "report_id": "cc2a723e-fc24-42d1-8ffc-2c76a5531512",
            "ai_summary_provider": "openai:gpt-4o"
        },
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "html_article",
            "name": "Unit42 Mallox",
            "tlp_level": "red",
            "confidence": 34,
            "labels": [
                "label2"
            ],
            "file_name": "html-real/unit42-mallox-ransomware.html",
            "report_id": "04aa52aa-4ba5-4e72-acd8-eb569da956d4",
            "ai_summary_provider": "openai:gpt-4o"
        },
    # Word
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "word",
            "name": "txt2stix local extractions docx",
            "tlp_level": "green",
            "confidence": 7,
            "labels": [
                "label1",
                "label2"
            ],
            "file_name": "doc/txt2stix-local-extractions.docx",
            "report_id": "2bd196b5-cc59-491d-99ee-ed5ea2002d61",
            "ai_summary_provider": "openai:gpt-4o"
        },
    # Powerpoint
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "powerpoint",
            "name": "fanged data pptx",
            "tlp_level": "green",
            "confidence": 56,
            "labels": [
                "label1",
                "label2"
            ],
            "file_name": "ppt/fanged_data.pptx",
            "report_id": "4dee1bac-801c-451f-a35d-b5dd7159ee5e",
            "ai_summary_provider": "openai:gpt-4o"
        }
    ]

    # Step 1: Delete any existing reports to avoid conflicts
    for test_case in test_cases:
        delete_report(test_case["report_id"])

    # Step 2: Run tests for each test case
    for test_case in test_cases:
        print(f"Running test for file '{test_case['file_name']}'")
        try:
            run_single_test(test_case)
        except requests.exceptions.HTTPError as e:
            print(f"Failed to upload file '{test_case['file_name']}': {e}")

# Run all tests
if __name__ == "__main__":
    run_all_tests()
