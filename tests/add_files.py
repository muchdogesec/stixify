import requests
import time

# Base URLs for API endpoints
BASE_URL = "http://127.0.0.1:8004/api/v1/"
FILES_ENDPOINT = f"{BASE_URL}files/"
JOBS_ENDPOINT = f"{BASE_URL}jobs/"

# Helper function to make the file upload request
def upload_file(profile_id, mode, name, tlp_level, confidence, labels, identity, file_path):
    with open(file_path, 'rb') as file:
        files = {
            'profile_id': (None, profile_id),
            'mode': (None, mode),
            'name': (None, name),
            'tlp_level': (None, tlp_level),
            'confidence': (None, str(confidence)),
            'labels': (None, ','.join(labels)),
            'identity': (None, identity),
            'file': (file_path, file, 'application/pdf'),
            'report_id': (None, report_id),
        }
        response = requests.post(FILES_ENDPOINT, files=files)
        response.raise_for_status()
        return response.json().get("id")

# Helper function to poll the job status until it's completed
def poll_job_status(job_id, max_retries=10, interval=5):
    for attempt in range(max_retries):
        response = requests.get(f"{JOBS_ENDPOINT}{job_id}")
        response.raise_for_status()
        job_status = response.json().get("jobs", [{}])[0]
        
        state = job_status.get("state")
        print(f"Attempt {attempt + 1}: Job {job_id} state is '{state}'")
        
        if state == "completed":
            print("Job completed successfully.")
            return job_status
        elif state in {"processing_failed", "retrieve_failed"}:
            raise RuntimeError(f"Job {job_id} failed with state: {state}")

        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete in time.")

# Main function to run the tests with two file uploads in sequence
def run_test():
    # Test values for the first file
    profile_id = "2919ca71-e60c-5aad-81f7-8cf561645d03"
    mode = "pdf"
    name = "Fanged data good PDF"
    tlp_level = "clear"
    confidence = 99
    labels = ["label1", "label2"]
    identity = '{"type":"identity","spec_version":"2.1","id":"identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5","name":"Dummy Identity"}'
    file_path = "path/to/fanged_data_good.pdf",
    report_id = "e7b435d3-cb2b-487a-bb16-8826441a89ed"

    # Upload the first file and retrieve the job ID
    job_id_1 = upload_file(profile_id, mode, name, tlp_level, confidence, labels, identity, file_path)
    print(f"First file uploaded successfully. Job ID: {job_id_1}")

    # Poll the job status of the first file until completed
    job_result_1 = poll_job_status(job_id_1)
    print("First job result:", job_result_1)

    # Placeholder: Values for the second file (can be modified)
    profile_id_2 = "another_profile_id"
    mode_2 = "pdf"
    name_2 = "Second data PDF"
    tlp_level_2 = "amber"
    confidence_2 = 85
    labels_2 = ["label3", "label4"]
    identity_2 = '{"type":"identity","spec_version":"2.1","id":"identity--12345678-9abc-def0-1234-56789abcdef0","name":"Second Dummy Identity"}'
    file_path_2 = "path/to/second_data.pdf"
    report_id = "be2f9355-11eb-4c28-8c8d-0e63f9b59773"

    # Upload the second file only after the first job completes
    job_id_2 = upload_file(profile_id_2, mode_2, name_2, tlp_level_2, confidence_2, labels_2, identity_2, file_path_2)
    print(f"Second file uploaded successfully. Job ID: {job_id_2}")

    # Poll the job status of the second file until completed
    job_result_2 = poll_job_status(job_id_2)
    print("Second job result:", job_result_2)

# Run the test function
if __name__ == "__main__":
    run_test()
