import requests
import pandas as pd
from tqdm import tqdm
import os
import zipfile
from lxml import etree
import time


# def collect_urls(start_date, end_date):
#     url = "https://developer.uspto.gov/products/bdss/get/ajax"
#     params = {
#         "data": f'{{"name":"APPXML","fromDate":"{start_date}","toDate":"{end_date}"}}'
#     }
#     response = requests.get(url, params=params, timeout=10)
#     if response.status_code != 200:
#         print(f"Error: {response.status_code}")
#         return []
#     print(f"Urls collected for the period from {start_date} to {end_date} successfully")
#     return response.json()["productFiles"]


def collect_urls(year):
    url = f"https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/{year}/"
    # params = {
    #     "data": f'{{"name":"APPXML","fromDate":"{start_date}","toDate":"{end_date}"}}'
    # }
    print(url)
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []
    # print(f"Urls collected for the period from {start_date} to {end_date} successfully")
    return response.json()["productFiles"]


def download_files(files, download_path):
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    for index, file in enumerate(files):
        file_url = file["fileDownloadUrl"]
        file_name = file["fileFromTime"] + "_" + file["fileName"].split(".")[0]
        zip_file_name = f"{file_name}.zip"
        zip_file_path = os.path.join(download_path, zip_file_name)
        try:
            response = requests.get(file_url, stream=True, timeout=10)
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {file_name}: {e}")
            print("Retrying after 60 seconds...")
            time.sleep(60)
            try:
                response = requests.get(file_url, stream=True, timeout=10)
            except requests.exceptions.RequestException as e:
                print(f"Error downloading {file_name} after retry: {e}")
                print("Retrying after 180 seconds...")
                time.sleep(180)
                response = requests.get(file_url, stream=True, timeout=10)

        with open(zip_file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded {file_name} ------- {index + 1} / {len(files)}")


def unzip_files(download_path, unzip_path):
    if not os.path.exists(unzip_path):
        os.makedirs(unzip_path)
    for file_name in tqdm(os.listdir(download_path), desc="Unzipping files"):
        if file_name.endswith(".zip"):
            zip_file_path = os.path.join(download_path, file_name)
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(unzip_path)
            print(f"Unzipped {file_name} to {unzip_path}")


def main():
    start_date = input("Enter start date YYYY-MM: ")
    end_date = input("Enter end date YYYY-MM: ")
    download_path = "patents_data"
    unzip_path = "unzipped_patents_data"

    files = collect_urls(start_date, end_date)
    if files:
        total_size = sum(file["fileSize"] / 1024 / 1024 for file in files)
        print(
            f"\nTotal file size: {round(total_size / 1024, 2)} GB between {start_date} and {end_date}\n"
        )
        download_files(files, download_path)
        unzip_files(download_path, unzip_path)


if __name__ == "__main__":
    main()
