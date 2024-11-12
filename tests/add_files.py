import requests
import time
import os

# Base URLs for API endpoints
BASE_URL = "http://127.0.0.1:8004/api/v1/"
FILES_ENDPOINT = f"{BASE_URL}files/"
JOBS_ENDPOINT = f"{BASE_URL}jobs/"
REPORTS_ENDPOINT = f"{BASE_URL}reports/"

# Directory path for files
FILES_DIR = os.path.join(os.path.dirname(__file__), "files/pdf")

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
def upload_file(profile_id, mode, name, tlp_level, confidence, labels, identity, file_path, report_id):
    with open(file_path, 'rb') as file:
        files = {
            'profile_id': (None, profile_id),
            'mode': (None, mode),
            'name': (None, name),
            'tlp_level': (None, tlp_level),
            'confidence': (None, str(confidence)),
            'labels': (None, ','.join(labels)),
            'identity': (None, identity),
            'file': (os.path.basename(file_path), file, 'application/pdf'),
            'report_id': (None, report_id),
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
        identity=test_case["identity"],
        file_path=file_path,
        report_id=test_case["report_id"]
    )
    print(f"File '{test_case['file_name']}' uploaded successfully. Job ID: {job_id}")
    
    # Poll the job status until completed
    job_result = poll_job_status(job_id)
    print(f"Job result for '{test_case['file_name']}':", job_result)

# Main function to run all test cases
def run_all_tests():
    # Define test cases as a list of dictionaries
    test_cases = [
        {
            "profile_id": "2919ca71-e60c-5aad-81f7-8cf561645d03",
            "mode": "pdf",
            "name": "Fanged data good PDF",
            "tlp_level": "clear",
            "confidence": 99,
            "labels": ["label1", "label2"],
            "identity": '{"type":"identity","spec_version":"2.1","id":"identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5","name":"Dummy Identity"}',
            "file_name": "fanged_data_good.pdf",
            "report_id": "6cb8665e-3607-4bbe-a9a3-c2a46bd13630"
        },
        {
            "profile_id": "3919da72-e60c-5aad-82f7-8cf561645d03",
            "mode": "pdf",
            "name": "Sample Report 2",
            "tlp_level": "amber",
            "confidence": 80,
            "labels": ["example_label"],
            "identity": '{"type":"identity","spec_version":"2.1","id":"identity--a123456b-f98c-5f4b-8d08-8ee04e02dbb5","name":"Another Identity"}',
            "file_name": "txt2stix-all-cases.pdf",
            "report_id": "b2869cb5-5270-4543-ac71-601cc8cd2e3b"
        },
        # Add more test cases as needed
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
