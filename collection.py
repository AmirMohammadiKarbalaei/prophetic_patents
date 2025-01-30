import requests
import pandas as pd
from tqdm import tqdm
import os
import zipfile
from lxml import etree


start_date = input("Enter start date YYYY-MM: ")  # "2022-01"
end_date = input("Enter end date YYYY-MM: ")  # "2022-02"
download_path = "patents_data"
unzip_path = "unzipped_patents_data"

url = "https://developer.uspto.gov/products/bdss/get/ajax"
params = {
    "data": f'{{"name":"APPXML","fromDate":"{start_date}","toDate":"{end_date}"}}'
}
response = requests.get(url, params=params, timeout=10)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
else:
    print(f"Urls collected for the period from {start_date} to {end_date} successfully")

data = response.json()
rows = []
for f in data["productFiles"]:
    rows.append(
        [
            f["fileFromTime"],
            f["fileName"],
            f["fileSize"] / 1000000,
            f["fileDownloadUrl"],
        ]
    )

total_size = sum(row[2] for row in rows)
print(
    f"\nTotal file size: {round(total_size / 1000, 2)} GB between {start_date} and {end_date}\n"
)


if not os.path.exists(download_path):
    os.makedirs(download_path)
if not os.path.exists(unzip_path):
    os.makedirs(unzip_path)


for index, row in enumerate(data["productFiles"]):
    file_url = row["fileDownloadUrl"]
    file_name = row["fileFromTime"] + "_" + row["fileName"].split(".")[0]
    zip_file_name = f"{file_name}.zip"
    zip_file_path = os.path.join(download_path, zip_file_name)

    response = requests.get(file_url, stream=True, timeout=10)
    with open(zip_file_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    print(f"Downloaded {file_name} ------- {index + 1} / {len(data['productFiles'])}")

for file_name in tqdm(os.listdir(download_path), desc="Unzipping files"):
    if file_name.endswith(".zip"):
        zip_file_path = os.path.join(download_path, file_name)
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(unzip_path)
        print(f"Unzipped {file_name} to {unzip_path}")
