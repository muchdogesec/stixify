import os
import requests

# List of file paths relative to the R2 bucket URL
file_paths = [
    "csv/csv-test.csv",
    "doc/fanged_data.doc",
    "doc/fanged_data.docx",
    "doc/txt2stix-local-extractions.docx",
    "doc/txt2stix-local-extractions.docx",
    "html-real/bitdefender-fragments-of-cross-platform-backdoor-hint-at-larger-mac-os-attack.html",
    "html-real/group-ib-0ktapus.html",
    "html-real/unit42-Fighting-Ursa-Luring-Targets-With-Car-for-Sale.html",
    "html-real/unit42-mallox-ransomware.html",
    "html-real/virustotal-malware-trends.html",
    "html/fanged_data.html",
    "image/example-1.png",
    "image/example-2.webp",
    "image/example-3.jpeg",
    "image/example-4.jpg",
    "image/test-image-1.png",
    "image/test-image-2.webp",
    "image/test-image-3.png",
    "markdown/threat-report.md",
    "pdf-real/bitdefender-rdstealer.pdf",
    "pdf-real/canadian-cert-qakbot.pdf",
    "pdf-real/crowdstrike-fancy-bear.pdf",
    "pdf-real/france-cert-apt31-1.pdf",
    "pdf-real/france-cert-apt31-2.pdf",
    "pdf-real/group-ib-ransomware-report.pdf",
    "pdf-real/mandiant-apt1-report.pdf",
    "pdf-real/norma-cyber-oil-gas.pdf",
    "pdf-real/rpt-apt30.pdf",
    "pdf-real/sophoslabs-mykings.pdf",
    "pdf-real/thai-cert-threat-actors.pdf",
    "pdf/fanged_data_good.pdf",
    "pdf/pdf-example.pdf",
    "pdf/txt2stix-local-extractions.pdf",
    "pdf/txt2stix-remote-lookups.pdf",
    "ppt/fanged_data.ppt",
    "ppt/fanged_data.pptx",
    "txt/threat-report.txt",
    "xls/fanged_data.xls",
    "xls/fanged_data.xlsx"
]

# Base URL for Cloudflare R2 bucket
base_url = "https://pub-99019d5e65d44129a12bd0448a6b6e64.r2.dev/"

# Directory to store downloaded files
base_directory = "tests/files"

# Function to download a file
def download_file(url, dest_path):
    try:
        # Make request to download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Write the content to the destination file
        with open(dest_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive new chunks
                    file.write(chunk)
        print(f"Downloaded: {url} -> {dest_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

# Ensure the base directory exists
os.makedirs(base_directory, exist_ok=True)

# Download all files while preserving the directory structure
for file_path in file_paths:
    # Full URL for the file
    file_url = base_url + file_path

    # Destination path (within the base directory)
    dest_path = os.path.join(base_directory, file_path)

    # Ensure the destination directory exists
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)

    # Download the file
    download_file(file_url, dest_path)

print("All files downloaded successfully.")
