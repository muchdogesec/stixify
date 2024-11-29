import requests

# API endpoint for dossiers
base_url = 'http://localhost:8004/api/v1/dossiers/'
headers = {
    'accept': 'application/json'
}

# Function to get all dossier IDs with pagination
def get_all_dossier_ids():
    dossier_ids = []
    page_number = 1

    while True:
        response = requests.get(base_url, headers=headers, params={'page': page_number})
        print(f"GET Request to {response.url}")
        print("Response Status:", response.status_code)
        print("Response Body:", response.json())

        if response.status_code == 200:
            data = response.json()
            dossier_ids.extend([dossier['id'] for dossier in data.get('dossiers', [])])

            # Check if there are more pages
            if data['page_results_count'] < data['page_size']:
                break
            page_number += 1
        else:
            print("Error fetching dossiers:", response.status_code, response.text)
            break

    return dossier_ids

# Function to delete a dossier by ID
def delete_dossier(dossier_id):
    delete_url = f"{base_url}{dossier_id}/"
    response = requests.delete(delete_url)
    print(f"DELETE Request to {delete_url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.text)

    return response.status_code == 204

# Function to verify that no dossiers remain
def verify_no_dossiers_remaining():
    response = requests.get(base_url, headers=headers)
    print(f"Final GET Request to {response.url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.json())

    if response.status_code == 200:
        data = response.json()
        if data.get('total_results_count', 0) == 0:
            print("Verification successful: No dossiers remaining.")
        else:
            print(f"Verification failed: {data['total_results_count']} dossiers remaining.")
    else:
        print("Error verifying dossiers:", response.status_code, response.text)

# Main logic
dossier_ids = get_all_dossier_ids()
for dossier_id in dossier_ids:
    delete_success = delete_dossier(dossier_id)
    if not delete_success:
        print(f"Failed to delete dossier with ID {dossier_id}")

# Final check to ensure no dossiers remain
verify_no_dossiers_remaining()
