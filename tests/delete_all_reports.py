import requests

# API endpoint for reports
base_url = 'http://localhost:8004/api/v1/reports/'
headers = {
    'accept': 'application/json'
}

# Function to get all report IDs with pagination
def get_all_report_ids():
    report_ids = []
    page_number = 1

    while True:
        response = requests.get(base_url, headers=headers, params={'page': page_number})
        print(f"GET Request to {response.url}")
        print("Response Status:", response.status_code)
        print("Response Body:", response.json())

        if response.status_code == 200:
            data = response.json()
            report_ids.extend([report['id'] for report in data.get('reports', [])])

            # Check if there are more pages
            if page_number * data['page_results_count'] >= data['total_results_count']:
                break
            page_number += 1
        else:
            print("Error fetching reports:", response.status_code, response.text)
            break

    return report_ids

# Function to delete a report by ID
def delete_report(report_id):
    delete_url = f"{base_url}{report_id}/"
    response = requests.delete(delete_url)
    print(f"DELETE Request to {delete_url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.text)

    return response.status_code == 204

# Function to verify that no reports remain
def verify_no_reports_remaining():
    response = requests.get(base_url, headers=headers)
    print(f"Final GET Request to {response.url}")
    print("Response Status:", response.status_code)
    print("Response Body:", response.json())

    if response.status_code == 200:
        data = response.json()
        if data.get('total_results_count', 0) == 0:
            print("Verification successful: No reports remaining.")
        else:
            print(f"Verification failed: {data['total_results_count']} reports remaining.")
    else:
        print("Error verifying reports:", response.status_code, response.text)

# Main logic
report_ids = get_all_report_ids()
for report_id in report_ids:
    delete_success = delete_report(report_id)
    if not delete_success:
        print(f"Failed to delete report with ID {report_id}")

# Final check to ensure no reports remain
verify_no_reports_remaining()
