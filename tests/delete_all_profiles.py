import requests

# API endpoint for profiles
base_url = 'http://localhost:8004/api/v1/profiles/'
headers = {
    'accept': 'application/json'
}

# Function to get all profile IDs with pagination
def get_all_profile_ids():
    profile_ids = []
    page_number = 1

    while True:
        response = requests.get(base_url, headers=headers, params={'page': page_number})
        print(f"GET Request to {response.url}")
        print("Response Status:", response.status_code)
        print("Response Body:", response.json())

        if response.status_code == 200:
            data = response.json()
            profile_ids.extend([profile['id'] for profile in data.get('profiles', [])])

            # Check if there are more pages
            if data['page_results_count'] < data['page_size']:
                break
            page_number += 1
        else:
            print("Error fetching profiles:", response.status_code, response.text)
            break

    return profile_ids

# Function to delete a profile by ID
def delete_profile(profile_id):
    delete_url = f"{base_url}{profile_id}/"
    response = requests.delete(delete_url)
    print(f"DELETE Request to {delete_url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.text)

    return response.status_code == 204

# Function to verify that no profiles remain
def verify_no_profiles_remaining():
    response = requests.get(base_url, headers=headers)
    print(f"Final GET Request to {response.url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.json())

    if response.status_code == 200:
        data = response.json()
        if data.get('total_results_count', 0) == 0:
            print("Verification successful: No profiles remaining.")
        else:
            print(f"Verification failed: {data['total_results_count']} profiles remaining.")
    else:
        print("Error verifying profiles:", response.status_code, response.text)

# Main logic
profile_ids = get_all_profile_ids()
for profile_id in profile_ids:
    delete_success = delete_profile(profile_id)
    if not delete_success:
        print(f"Failed to delete profile with ID {profile_id}")

# Final check to ensure no profiles remain
verify_no_profiles_remaining()
