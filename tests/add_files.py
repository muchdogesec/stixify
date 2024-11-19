import argparse
import requests
import time
import os
import traceback
import sys

# Base URLs for API endpoints
BASE_URL = "http://127.0.0.1:8004/api/v1/"
FILES_ENDPOINT = f"{BASE_URL}files/"
JOBS_ENDPOINT = f"{BASE_URL}jobs/"
REPORTS_ENDPOINT = f"{BASE_URL}reports/"

# Directory path for files
FILES_DIR = os.path.join(os.path.dirname(__file__), "files")

# Function to validate server connection
def validate_server():
    try:
        print("Validating server connection...")
        response = requests.get(BASE_URL)
        print(f"Server response: {response.status_code}")
        if response.status_code != 200:
            print("Warning: Server is reachable, but response code is not 200.")
    except requests.exceptions.RequestException as e:
        print(f"Error: Unable to connect to the server at {BASE_URL}")
        traceback.print_exc()
        sys.exit(2)  # Exit with error code 2 for server connection issues

# Validate input report IDs
def validate_report_ids(input_ids, test_cases):
    valid_ids = {tc["report_id"] for tc in test_cases}
    for report_id in input_ids:
        if report_id not in valid_ids:
            print(f"Error: Invalid report ID '{report_id}'.")
            print("Valid report IDs are:")
            for valid_id in valid_ids:
                print(f"  - {valid_id}")
            sys.exit(1)  # Exit with error code 1 for invalid input

# Function to delete a report by its ID
def delete_report(report_id):
    try:
        delete_url = f"{REPORTS_ENDPOINT}{report_id}/"
        print(f"Attempting to delete report: {report_id}")
        response = requests.delete(delete_url)
        print(f"DELETE Request to {delete_url}")
        print(f"Response Status Code: {response.status_code}")
        if response.status_code == 204:
            print(f"Report {report_id} deleted successfully.")
        else:
            print(f"Failed to delete report {report_id}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error while deleting report {report_id}")
        traceback.print_exc()

# Helper function to upload a file
def upload_file(profile_id, mode, name, tlp_level, confidence, labels, file_path, report_id, ai_summary_provider):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)  # Exit for missing file

    try:
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
            print(f"Uploading file: {file_path}")
            response = requests.post(FILES_ENDPOINT, files=files)
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()
            return response.json().get("id")
    except requests.exceptions.RequestException as e:
        print(f"Error during file upload for '{file_path}'")
        traceback.print_exc()
        sys.exit(1)  # Exit for upload failure

# Poll the job status
def poll_job_status(job_id, max_retries=10, interval=30):
    for attempt in range(max_retries):
        try:
            print(f"Polling job status (Attempt {attempt + 1}) for Job ID: {job_id}")
            response = requests.get(f"{JOBS_ENDPOINT}{job_id}")
            print(f"GET Request to: {JOBS_ENDPOINT}{job_id}")
            print(f"Response Status Code: {response.status_code}")
            response.raise_for_status()
            job_status = response.json()
            state = job_status.get("state")
            print(f"Job state: {state}")
            if state == "completed":
                print("Job completed successfully.")
                return job_status
            elif state in {"processing_failed", "retrieve_failed"}:
                print(f"Job {job_id} failed with state: {state}")
                sys.exit(1)  # Exit for job failure
            time.sleep(interval)
        except Exception as e:
            print(f"Error while polling job status for Job ID: {job_id}")
            traceback.print_exc()
    print(f"Timeout: Job {job_id} did not complete within the expected time.")
    sys.exit(1)  # Exit for timeout

# Run a single test case
def run_single_test(test_case):
    file_path = os.path.join(FILES_DIR, test_case["file_name"])
    print(f"Running test for file: {file_path}")
    try:
        job_id = upload_file(
            profile_id=test_case["profile_id"],
            mode=test_case["mode"],
            name=test_case["name"],
            tlp_level=test_case["tlp_level"],
            confidence=test_case["confidence"],
            labels=test_case["labels"],
            file_path=file_path,
            report_id=test_case["report_id"],
            ai_summary_provider=test_case["ai_summary_provider"],
        )
        print(f"File uploaded. Job ID: {job_id}")
        poll_job_status(job_id)
    except Exception as e:
        print(f"Test failed for file '{test_case['file_name']}'")
        traceback.print_exc()

# Main function
def run_tests(test_cases, selected_report_ids=None):
    print("Starting test execution...")
    validate_server()
    if selected_report_ids:
        print(f"Validating selected report IDs: {selected_report_ids}")
        validate_report_ids(selected_report_ids, test_cases)
        test_cases = [tc for tc in test_cases if tc["report_id"] in selected_report_ids]
        if not test_cases:
            print("No test cases matched the provided report IDs.")
            sys.exit(1)
    print(f"Running {len(test_cases)} test case(s)...")
    for test_case in test_cases:
        delete_report(test_case["report_id"])
        run_single_test(test_case)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run file upload tests.")
    parser.add_argument(
        "--report-ids",
        nargs="*",
        help="List of report IDs to run tests for. If not specified, all tests will run.",
    )
    args = parser.parse_args()

    # Define test cases as a list of dictionaries
    test_cases = [
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
            "report_id": "report--6cb8665e-3607-4bbe-a9a3-c2a46bd13630",
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
            "report_id": "report--b2869cb5-5270-4543-ac71-601cc8cd2e3b",
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
            "report_id": "report--aaec934b-9141-4ff7-958b-3b99a7b24234",
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
            "report_id": "report--65ba4fa9-dfff-4597-bcb9-eb749bb84642",
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
            "report_id": "report--5795e067-72a4-4953-87ed-f6c56dc6f639",
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
            "report_id": "report--cc2a723e-fc24-42d1-8ffc-2c76a5531512",
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
            "report_id": "report--04aa52aa-4ba5-4e72-acd8-eb569da956d4",
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
            "report_id": "report--2bd196b5-cc59-491d-99ee-ed5ea2002d61",
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
            "report_id": "report--4dee1bac-801c-451f-a35d-b5dd7159ee5e",
            "ai_summary_provider": "openai:gpt-4o"
        }
    ]

    try:
        run_tests(test_cases, selected_report_ids=args.report_ids)
    except Exception as e:
        print("An unexpected error occurred during test execution.")
        traceback.print_exc()
        sys.exit(1)  # Exit for any unexpected errors

