import requests
import os
import zipfile
from lxml import etree
from tqdm import tqdm
import re
from utilities.nlp_processing import dic_to_dic_w_tense_test
from utilities.database_utils import store_patent_examples, store_patent_statistics
from utilities.utils_clean import (
    remove_leadiong_zeros,
    find_doc_number,
    extract_experiments_w_heading,
    extract_examples_start_w_word,
    remove_duplicate_docs,
)
import argparse
from bs4 import BeautifulSoup
import time


# Custom tqdm class that reports progress to a callback function
class TqdmCallback(tqdm):
    def __init__(self, *args, **kwargs):
        # Extract callback before passing to parent
        self.callback = kwargs.pop("callback", None)
        self.last_update_time = time.time()
        self.update_interval = 0.5  # Update GUI every 0.5 seconds to avoid flooding
        super().__init__(*args, **kwargs)

    def display(self, msg=None, pos=None):
        # Call the parent class display method
        super().display(msg, pos)

        # Only send updates to GUI at a reasonable interval
        current_time = time.time()
        if (
            self.callback
            and current_time - self.last_update_time >= self.update_interval
        ):
            progress_msg = f"Progress: {self.n}/{self.total} {self.desc} [{int(self.n / self.total * 100)}%]"
            self.callback(progress_msg)
            self.last_update_time = current_time


def validate_kind(value, callback=None):
    """Validate if the kind is either 'application' or 'grant'."""
    try:
        if value not in ["application", "grant"]:
            if callback:
                callback(
                    f"Invalid kind value: {value}. Must be 'application' or 'grant'"
                )
            raise argparse.ArgumentTypeError(
                "Kind must be either 'application' or 'grant'"
            )
        if callback:
            callback(f"Valid kind selected: {value}")
        return value
    except Exception as e:
        if callback:
            callback(f"Validation error: {str(e)}")
        raise


def validate_year(year, callback=None):
    """Validate if the year is between 1976 and 2025."""
    try:
        year = int(year)
        if 1976 <= year <= 2025:
            if callback:
                callback(f"Valid year: {year}")
            return year
        if callback:
            callback(f"Invalid year: {year}. Must be between 1976 and 2025")
        raise ValueError
    except ValueError:
        if callback:
            callback(f"Invalid year format or value: {year}")
        raise argparse.ArgumentTypeError("Year must be between 1976 and 2025")


def get_latest_versions(urls, kind="g"):
    """
    Function to extract the latest versions of files based on a regex pattern.

    Args:
    - urls (dict): A dictionary where keys are years and values are lists of filenames.

    Returns:
    - latest_files (dict): A dictionary where keys are years and values are lists of the latest versions of the files for that year.
    """
    # Initialize the result dictionary to store the latest versions for each year
    latest_files = {}

    if kind == "g":
        pattern = re.compile(r"(ipg\d{6})(?:_r(\d+))?\.zip")
    elif kind == "a":
        pattern = re.compile(r"(ipa\d{6})(?:_r(\d+))?\.zip")

    # Process each year in the input dictionary

    latest_versions = {}  # Holds the latest version of files for the current year
    for file in urls:
        match = pattern.match(file)
        if match:
            base_name, revision = match.groups()
            revision = int(revision) if revision else 0  # Default to 0 if no revision

            # Extract the current highest revision number for the base_name
            current_revision_match = re.search(
                r"_r(\d+)", latest_versions.get(base_name, "")
            )
            current_revision = (
                int(current_revision_match.group(1)) if current_revision_match else 0
            )

            # Update if the new file has a higher revision
            if base_name not in latest_versions or revision > current_revision:
                latest_versions[base_name] = file

    # Get the final list of unique latest versions sorted by file name
    latest_files = sorted(latest_versions.values())

    return latest_files


def download_patents_pto(
    year, kind="application", download_path=None, callback=None, stop_event=None
):
    """Download patent files with progress updates."""
    try:
        if download_path is None:
            download_path = f"./data/patent_{kind}_{year}_zip"
        # if callback:
        #     callback(f"Starting download for year {year}...")

        url = f"https://bulkdata.uspto.gov/data/patent/{kind}/redbook/fulltext/{year}/"
        if callback:
            callback("Connecting to USPTO server...")

        rp = requests.get(url, timeout=10)
        root = etree.fromstring(rp.text.encode(), etree.XMLParser(recover=True))
        href_values = root.findall(".//a[@href]")
        urls = [
            href.get("href")
            for href in href_values
            if href.get("href").endswith(".zip")
        ]

        if callback:
            callback(f"Found {len(urls)} zip files for {year}")

        url_no_dup = get_latest_versions(urls, kind[0])
        # if callback:
        #     callback(f"Downloading {len(url_no_dup)} unique patent files...")

        download_files(url, download_path, url_no_dup, callback, stop_event)
        return True, download_path

    except requests.exceptions.RequestException as e:
        if callback:
            callback(f"Error during download: {e}")
        return False, ""


def download_files(url, download_path, files, callback=None, stop_event=None):
    """Download files with progress updates."""
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    for index, file_name in enumerate(files):
        if stop_event and stop_event.is_set():
            if callback:
                callback("Download stopped by user.")
            break

        if callback:
            callback(f"Downloading file {index + 1} of {len(files)}: {file_name}")

        url_ = url + file_name
        zip_file_path = os.path.join(download_path, file_name)

        response = requests.get(url_, stream=True, timeout=10)
        with open(zip_file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


def unzip_files(download_path, unzip_path, callback=None, stop_event=None):
    """Unzip files with progress updates."""
    if not os.path.exists(unzip_path):
        os.makedirs(unzip_path)
    try:
        files = [f for f in os.listdir(download_path) if f.endswith(".zip")]
        if callback:
            callback(f"Found {len(files)} zip files to extract")

        for file_name in files:
            if stop_event and stop_event.is_set():
                if callback:
                    callback("Unzip process stopped by user.")
                return False

            if callback:
                callback(f"Extracting {file_name}...")

            zip_file_path = os.path.join(download_path, file_name)
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(unzip_path)

        if callback:
            callback(f"Finished extracting all files to {unzip_path}")
        return True
    except Exception as e:
        if callback:
            callback(f"Error during unzip: {e}")
        return False


def extract_and_save_examples_in_db(folder_path, callback=None, stop_event=None):
    """Extract and save examples with progress updates."""
    if callback:
        callback("Starting example extraction process...")

    total_num_of_patents = 0
    total_examples_extracted = 0

    file_names = os.listdir(folder_path)

    for i, file in enumerate(file_names):
        if stop_event and stop_event.is_set():
            if callback:
                callback("Processing stopped by user.")
            return

        doc_w_exp = {}  # Reset for each file
        found_heading = 0
        not_found_heading = 0
        all_xml_parts = []

        if file.endswith(".xml"):
            if callback:
                callback(f"Processing file {i + 1} of {len(file_names)}: {file}")
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
                    parts = [p for p in parts if p.strip()]
                    all_xml_parts.extend(parts)
            except Exception as e:
                if callback:
                    callback(f"Error processing {file}: {str(e)}")
                continue

            xml_no_dup = remove_duplicate_docs(all_xml_parts)
            current_file_patents = len(xml_no_dup)
            total_num_of_patents += current_file_patents
            if callback:
                callback(
                    f"Found {current_file_patents} unique patents in current file."
                )

            for j, xml in enumerate(xml_no_dup):
                if stop_event and stop_event.is_set():
                    if callback:
                        callback("Processing stopped by user.")
                    return

                if callback:
                    if current_file_patents - j < 500:
                        callback(
                            f"Processed {current_file_patents}/{current_file_patents} patents in current file..."
                        )
                    if j % 500 == 0 and j > 1:  # More frequent progress updates
                        callback(
                            f"Processed {j}/{current_file_patents} patents in current file..."
                        )

                if len(xml) <= 2000:
                    pass

                s_tags = re.findall(r"<s\d+>.*?</s\d+>", xml)
                if len(s_tags) > 0 or '<sequence-cwu id="SEQLST-0">' in xml:
                    pass

                heading = extract_experiments_w_heading(xml)

                # Process examples based on heading presence
                if heading and len(heading) == 1:
                    found_heading += 1
                    examples = extract_examples_start_w_word(
                        heading[0].find_next_siblings()
                    )
                    if len(examples) == 0:
                        soup = BeautifulSoup(xml, "xml")
                        siblings = soup.find_all(["heading", "p"])
                        examples = extract_examples_start_w_word(siblings)
                else:
                    not_found_heading += 1
                    soup = BeautifulSoup(xml, "xml")
                    siblings = soup.find_all(["heading", "p"])
                    examples = extract_examples_start_w_word(siblings)

                if len(examples) > 0:
                    doc_num = remove_leadiong_zeros(find_doc_number(xml)[0])
                    doc_w_exp[doc_num] = examples

            # Store data after processing each file
            if doc_w_exp:
                if callback:
                    callback(f"Found {len(doc_w_exp)} patents with examples")
                try:
                    if callback:
                        callback("Starting tense classification...")

                    with_tense = dic_to_dic_w_tense_test(doc_w_exp)

                    if callback:
                        callback(
                            f"Classification complete, found {len(with_tense)} results"
                        )
                        # Verify structure of tense data
                        if with_tense:
                            sample_key = next(iter(with_tense.keys()))
                            sample_value = with_tense[sample_key]
                            callback(
                                f"Sample tense data: Patent {sample_key} → {sample_value}"
                            )

                    # Ensure data has expected structure before storage
                    if with_tense:
                        if callback:
                            callback(
                                f"Storing {len(with_tense)} patent statistics records..."
                            )
                        store_patent_examples(doc_w_exp)
                        store_patent_statistics(with_tense)
                        total_examples_extracted += len(doc_w_exp)
                    else:
                        if callback:
                            callback(
                                "No tense data was generated, skipping database storage"
                            )

                except Exception as e:
                    if callback:
                        callback(f"Error during tense classification: {str(e)}")
                    import traceback

                    if callback:
                        callback(traceback.format_exc())

    if callback:
        callback(
            f"Processing complete. Total patents processed: {total_num_of_patents}"
        )
        callback(f"Total examples extracted and stored: {total_examples_extracted}")
