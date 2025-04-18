import requests

# API endpoint
base_url = 'http://localhost:8004/api/v1/files/'
headers = {
    'accept': 'application/json'
}

# Function to get all file IDs with pagination
def get_all_file_ids():
    file_ids = []
    page_number = 1

    while True:
        response = requests.get(base_url, headers=headers, params={'page': page_number})
        print(f"GET Request to {response.url}")
        print("Response Status:", response.status_code)
        print("Response Body:", response.json())

        if response.status_code == 200:
            data = response.json()
            file_ids.extend([file['id'] for file in data.get('files', [])])

            # Check if there are more pages
            if data['page_results_count'] < data['page_size']:
                break
            page_number += 1
        else:
            print("Error fetching files:", response.status_code, response.text)
            break

    return file_ids

# Function to delete a file by ID
def delete_file(file_id):
    delete_url = f"{base_url}{file_id}/"
    response = requests.delete(delete_url)
    print(f"DELETE Request to {delete_url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.text)

    return response.status_code == 204

# Function to verify that no files remain
def verify_no_files_remaining():
    response = requests.get(base_url, headers=headers)
    print(f"Final GET Request to {response.url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.json())

    if response.status_code == 200:
        data = response.json()
        if data.get('total_results_count', 0) == 0:
            print("Verification successful: No files remaining.")
        else:
            print(f"Verification failed: {data['total_results_count']} files remaining.")
    else:
        print("Error verifying files:", response.status_code, response.text)

# Main logic
file_ids = get_all_file_ids()
for file_id in file_ids:
    delete_success = delete_file(file_id)
    if not delete_success:
        print(f"Failed to delete file with ID {file_id}")

# Final check to ensure no files remain
verify_no_files_remaining()