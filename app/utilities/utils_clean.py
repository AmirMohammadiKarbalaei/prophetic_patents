import json
import os
import re
import argparse
import requests
from bs4 import BeautifulSoup
from lxml import etree

import pandas as pd
from tqdm import tqdm
import zipfile
import pickle

from utilities.database_utils import store_patent_examples, store_patent_statistics
from utilities.nlp_processing import dic_to_dic_w_tense_test


# region General utils


def remove_leadiong_zeros(s):
    s = s.replace("[", "").replace("]", "").replace("'", "").replace(" ", "")

    if len(s) == 8 and s.startswith("0"):
        s = s[1:]
    return s


def validate_kind(value):
    """Validate if the kind is either 'application' or 'grant'."""
    if value not in ["application", "grant"]:
        raise argparse.ArgumentTypeError("Kind must be either 'application' or 'grant'")
    return value


def validate_year(year):
    """Validate if the year is between 1976 and 2025."""
    try:
        year = int(year)
        if 1976 <= year <= 2025:
            return year
        raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("Year must be between 1976 and 2025")


def save_as_pickle(test_dataset, filename="test_dataset.pkl"):
    """Save the test dataset using pickle."""
    with open(filename, "wb") as f:
        pickle.dump(test_dataset, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Saved {len(test_dataset)} patents to {filename}")


def load_from_pickle(filename="test_dataset.pkl"):
    """Load the test dataset from a pickle file."""
    with open(filename, "rb") as f:
        data = pickle.load(f)
    print(f"Loaded {len(data)} patents from {filename}")
    return data


def clean_dict_keys_test_dataset(data):
    new_dict = {}

    for key, value in data.items():
        # Step 1: Remove '[', ']', and spaces
        cleaned_key = (
            key.replace("[", "").replace("]", "").replace("'", "").replace(" ", "")
        )

        # Step 2: If length is 8, check first character
        if len(cleaned_key) == 8 and cleaned_key.startswith("0"):
            cleaned_key = cleaned_key[1:]  # Remove leading zero

        # Step 3: Assign new key to the dictionary
        new_dict[cleaned_key] = value

    return new_dict


def save_xml_string(xml_string, filepath="test.xml"):
    """Save a string containing XML content to a file"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(xml_string)


def read_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def read_xlsb_file(path="Freilich.Data.Compressed.xlsb"):
    import xlwings as xw

    app = xw.App(visible=False)
    workbook = app.books.open(path)
    sheet = workbook.sheets[1]  # Or use sheet name
    data = sheet.range("A1").expand().value
    df = pd.DataFrame(data[1:], columns=data[0])
    workbook.close()
    app.quit()
    return df


def save_as_json(examples, filename="1200_patents_w_experiments.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=4, ensure_ascii=False)
    print(f"Saved as {filename}")


def read_xml_file(file_path):
    """
    Read the content of an XML file.

    Args:
        file_path (str): Path to the XML file

    Returns:
        str: Content of the XML file
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    return content


# region Utils
def extract_ipc_dic(ipc_path="../temp/EN_ipc_title_list_20250101"):
    file_names = os.listdir(ipc_path)
    ipc_dict = {}
    for file_name in file_names:
        with open(ipc_path + "/" + file_name, "r", encoding="utf-8") as file:
            lines = file.readlines()  # each line becomes an element in a list
            lines = [line.strip() for line in lines]
        dic = {
            line.split("\t")[0]: line.split("\t")[1]
            for line in lines[1:]
            if "\t" in line[:4]
        }
        ipc_dict[file_name.split("_")[3]] = dic
    return ipc_dict


def unzip_files(download_path, unzip_path):
    if not os.path.exists(unzip_path):
        os.makedirs(unzip_path)
    try:
        for file_name in tqdm(os.listdir(download_path), desc="Unzipping files"):
            if file_name.endswith(".zip"):
                zip_file_path = os.path.join(download_path, file_name)
                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    zip_ref.extractall(unzip_path)
                print(f"Unzipped {file_name} to {unzip_path}")
        return True
    except Exception as e:
        print(f"Error during unzip: {e}")
        return False


def find_doc_number(xml_part):
    root = etree.fromstring(xml_part.encode(), etree.XMLParser(recover=True))
    doc_num = root.xpath("//publication-reference//document-id//doc-number/text()")
    return doc_num


def find_patent_number(xml_part):
    root = etree.fromstring(xml_part.encode(), etree.XMLParser(recover=True))
    # patent_num = root.xpath("//application-reference//document-id//doc-number/text()")
    patent_num = root.xpath(
        "//continuation-in-part//parent-grant-document//document-id//doc-number/text()"
    )
    return patent_num


def remove_duplicate_docs(xml_parts):
    """
    Remove duplicate documents keeping only the longest version.

    Args:
        xml_parts (list): List of XML documents

    Returns:
        list: XML documents with duplicates removed
    """
    doc_versions = {}

    for xml in xml_parts:
        doc_num = find_doc_number(xml)[0]
        if doc_num not in doc_versions or len(xml) > len(doc_versions[doc_num]):
            doc_versions[doc_num] = xml

    return list(doc_versions.values())


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


def process_xml_files(directory_path):
    """
    Process all XML files in the given directory and split them into parts.

    Args:
        directory_path (str): Path to directory containing XML files

    Returns:
        list: Combined list of XML parts from all files
    """
    all_xml_parts = []

    # Get all XML files in directory
    xml_files = [f for f in os.listdir(directory_path) if f.endswith(".xml")]

    # Process each file
    for xml_file in xml_files:
        file_path = os.path.join(directory_path, xml_file)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
                # Remove empty parts and extend master list
                parts = [p for p in parts if p.strip()]
                all_xml_parts.extend(parts)
        except Exception as e:
            print(f"Error processing {xml_file}: {str(e)}")

    return all_xml_parts


# region Data collection


def download_files(url, download_path, files):
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    for index, file_name in enumerate(files):
        url_ = url + file_name

        zip_file_path = os.path.join(download_path, file_name)  # .split(".")[-1]
        response = requests.get(url_, stream=True, timeout=10)
        with open(zip_file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded {file_name} ------- {index + 1} / {len(files)}")


def download_patents_pto(year, kind="application", download_path=None):
    try:
        if download_path is None:
            download_path = f"data/patent_{kind}_{year}_zip"
        urls = {}
        url = f"https://bulkdata.uspto.gov/data/patent/{kind}/redbook/fulltext/{year}/"
        rp = requests.get(url, timeout=10)
        root = etree.fromstring(rp.text.encode(), etree.XMLParser(recover=True))
        href_values = root.findall(".//a[@href]")
        urls = [
            href.get("href")
            for href in href_values
            if href.get("href").endswith(".zip")
        ]
        url_no_dup = get_latest_versions(urls, kind[0])
        download_files(url, download_path, url_no_dup)
        return True, download_path

    except requests.exceptions.RequestException as e:
        print(f"Error during download: {e}")
        return False, ""


def extract_classify_num_patents_w_experiments(
    folder_path="D:\\unzipped_patents_23_24",
):
    # https://dimensions.freshdesk.com/support/solutions/articles/23000018832-what-are-the-ipcr-and-cpc-patent-classifications- (IPCR AND CPC CLASSIFICATIONS)

    ipc_sector_map = {
        "A": "Human Necessities",
        "B": "Performing Operations; Transporting",
        "C": "Chemistry; Metallurgy",
        "D": "Textiles; Paper",
        "E": "Fixed Constructions",
        "F": "Mechanical Engineering; Lighting; Heating",
        "G": "Physics",
        "H": "Electricity",
        "Unknown Sector": "Unknown Sector",
        "Not Found": "Not Found",
    }
    ipc_dic = extract_ipc_dic()

    sectors_dict = {
        sector: {"examples": 0, "without_examples": 0}
        for sector in ipc_sector_map.values()
    }

    file_names = os.listdir(folder_path)
    total_num_of_patents = 0
    for i, file in enumerate(file_names):
        all_xml_parts = []
        if file.endswith(".xml"):
            print(f"Processing {file}... ({i + 1}/{len(file_names)})")
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
                    parts = [p for p in parts if p.strip()]
                    all_xml_parts.extend(parts)
            except Exception as e:
                print(f"Error processing {file}: {str(e)}")
            # xml_no_dup = remove_duplicate_docs(all_xml_parts)
            # print(f"Num of duplicates removed: {len(all_xml_parts) - len(xml_no_dup)} out of {len(all_xml_parts)}")
            total_num_of_patents += len(all_xml_parts)
            for j, xml in enumerate(all_xml_parts):
                if j % 2000 == 0:
                    total_without_examples = sum(
                        sector["without_examples"] for sector in sectors_dict.values()
                    )
                    total_with_examples = sum(
                        sector["examples"] for sector in sectors_dict.values()
                    )
                    print(
                        f"Total without examples: {total_without_examples}, Total with examples: {total_with_examples}, Total patents: {total_num_of_patents}"
                    )
                    print(f"Processed {j} out of {len(all_xml_parts)}")

                root = etree.fromstring(xml.encode(), etree.XMLParser(recover=True))
                try:
                    section = root.xpath(
                        "//classifications-ipcr/classification-ipcr/section/text()"
                    )[0]
                    sector = ipc_sector_map.get(section, "Unknown Sector")

                except IndexError:
                    sector = "Not Found"

                # Update the counts in the dictionary
                if extract_experiments_w_heading(xml):
                    sectors_dict[sector]["with_examples"] += 1
                else:
                    sectors_dict[sector]["without_examples"] += 1
    return sectors_dict


# region Experiments section
def extract_and_save_examples_in_db(
    folder_path="D:\\unzipped_patents_23_24",
):
    # https://dimensions.freshdesk.com/support/solutions/articles/23000018832-what-are-the-ipcr-and-cpc-patent-classifications- (IPCR AND CPC CLASSIFICATIONS)
    doc_w_exp = {}
    found_heading = 0
    not_found_heading = 0

    file_names = os.listdir(folder_path)
    total_num_of_patents = 0
    for i, file in enumerate(file_names):
        all_xml_parts = []
        if file.endswith(".xml"):
            print(f"Processing {file}... ({i + 1}/{len(file_names)})")
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
                    parts = [p for p in parts if p.strip()]
                    all_xml_parts.extend(parts)
            except Exception as e:
                print(f"Error processing {file}: {str(e)}")
            # xml_no_dup = remove_duplicate_docs(all_xml_parts)
            # print(f"Num of duplicates removed: {len(all_xml_parts) - len(xml_no_dup)} out of {len(all_xml_parts)}")
            total_num_of_patents += len(all_xml_parts)
            for j, xml in enumerate(all_xml_parts):
                if j % 1000 == 0 and j > 1:
                    print(f"Processed {j}/{len(all_xml_parts)}...")
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
            print(
                f"\nExtracted examples from {len(doc_w_exp)} patents out of {total_num_of_patents} patents"
            )
            print("\nClassifying  Examples ......")
            try:
                with_tense = dic_to_dic_w_tense_test(doc_w_exp)
                print("Classified examples successfully")
            except Exception as e:
                print(f"Error classifying examples: {e}")
            print("\nStoring Examples in Database ......")
            try:
                store_patent_examples(doc_w_exp)
                store_patent_statistics(with_tense)
                print("Stored examples in database successfully")
            except Exception as e:
                print(f"Error storing examples in database: {e}")


def extract_num_dot_examples(text):
    soup = BeautifulSoup(text, "xml")

    examples = {}
    current_heading = None
    current_text = []

    elements = soup.find_all(["heading", "p"])

    for element in elements:
        text = element.text.strip()

        # Check if the paragraph starts with a numbered section (e.g., "1. ", "2. ")
        if re.match(r"^\d+\.\s+", text):
            # Save previous section
            if current_heading:
                examples[current_heading] = " ".join(current_text)

            # Start a new section with this as the heading
            current_heading = f"Example {len(examples) + 1}: {text}"
            current_text = []
        else:
            # Add paragraph content to the current section
            current_text.append(text)

    # Add last section if exists
    if current_heading:
        examples[current_heading] = " ".join(current_text)

    return examples


def extract_experiments_w_heading(text):
    """Extracts all 'Examples/Experiments' sections from a patent text."""

    # Use BeautifulSoup to parse the structure
    soup = BeautifulSoup(text, "xml")

    # Find all "EXAMPLES/EXPERIMENTS" section headings
    examples_headings = soup.findAll(
        lambda tag: tag.name == "heading"
        and tag.text.strip().upper().replace(" ", "")
        in [
            "EXAMPLES",
            # "EXAMPLE",
            # "EXPERIMENT",
            "EXPERIMENTS",
            "TESTS",
        ]
    )
    # examples_headings = soup.findAll(
    #     lambda tag: tag.name == "heading"
    #     and any(
    #         keyword in tag.text.upper().replace(" ", "")
    #         for keyword in [
    #             "EXAMPLES",
    #             # "EXAMPLE",
    #             # "EXPERIMENT",
    #             "EXPERIMENTS",
    #             "Tests",
    #         ]
    #     )
    # )

    if not examples_headings:
        return None

    return examples_headings


def extract_examples_start_w_word(xml_siblings):
    examples = []
    current_example = None
    in_example = False

    for tag in xml_siblings:
        if tag.name == "heading":
            if (
                tag.text.strip().lower().startswith("example")
                or tag.text.strip().lower().startswith("experiment")
                or tag.text.strip().lower().startswith("test")
            ):
                in_example = True
                current_example = {
                    "number": tag.text.strip(),
                    "title": xml_siblings[xml_siblings.index(tag) + 1].text.strip(),
                    "content": [],
                }
                examples.append(current_example)
        elif tag.name == "heading" and (
            tag.text.strip().lower().startswith("example")
            or tag.text.strip().lower().startswith("experiment")
            or tag.text.strip().lower().startswith("test")
        ):
            in_example = False
        # else:
        #     # If we hit any other heading, stop collecting content
        #     in_example = False
        elif in_example and current_example is not None:
            current_example["content"].append(tag.text.strip())

    return examples


def extract_examples_w_word(text):
    """Find all example/experiment/test sections and extract their content"""
    soup = BeautifulSoup(text, "xml")
    examples = []

    # Find all matching headings
    example_headings = soup.findAll(
        lambda tag: tag.name == "heading"
        and any(
            keyword in tag.text.strip().lower().replace(" ", "")
            for keyword in ["example", "experiment", "test"]
        )
        # and not any(
        #     excluded in tag.text.strip().lower().replace(" ", "")
        #     for excluded in ["reference", "preparation"]
        # )
    )

    for heading in example_headings:
        current_content = []
        next_sibling = heading.find_next_sibling()

        # Get title from next heading
        title = (
            next_sibling.text.strip()
            if next_sibling and next_sibling.name == "heading"
            else ""
        )

        # Collect content until next example/section heading
        sibling = next_sibling
        while sibling and not (
            sibling.name == "heading"
            and any(
                keyword in sibling.text.strip().lower().replace(" ", "")
                for keyword in ["example", "experiment", "test"]
            )
            # and not any(
            #     excluded in sibling.text.strip().lower().replace(" ", "")
            #     for excluded in ["reference", "preparation"]
            # )
        ):
            if sibling.name == "p":
                current_content.append(sibling.text.strip())
            sibling = sibling.find_next_sibling()

        examples.append(
            {"number": heading.text.strip(), "title": title, "content": current_content}
        )

    return examples if examples else None


def process_siblings(xml_siblings):
    examples = []

    # Find all matching headings directly from xml_siblings
    example_headings = [
        tag
        for tag in xml_siblings
        if tag.name == "heading"
        and any(
            keyword in tag.text.strip().lower().replace(" ", "")
            for keyword in ["example", "experiment", "test"]
        )
        # and not any(
        #     excluded in tag.text.strip().lower().replace(" ", "")
        #     for excluded in ["reference", "preparation"]
        # )
    ]

    for heading in example_headings:
        current_content = []
        idx = xml_siblings.index(heading)

        # Get title from next heading if available
        title = ""
        if idx + 1 < len(xml_siblings) and xml_siblings[idx + 1].name == "heading":
            title = xml_siblings[idx + 1].text.strip()

        # Collect content until next example heading
        i = idx + 1
        while i < len(xml_siblings):
            if (
                xml_siblings[i].name == "heading"
                and any(
                    keyword in xml_siblings[i].text.strip().lower().replace(" ", "")
                    for keyword in ["example", "experiment", "test"]
                )
                # and not any(
                #     excluded in xml_siblings[i].text.strip().lower().replace(" ", "")
                #     for excluded in ["reference", "preparation"]
                # )
            ):
                break
            if xml_siblings[i].name == "p":
                current_content.append(xml_siblings[i].text.strip())
            i += 1

        examples.append(
            {"number": heading.text.strip(), "title": title, "content": current_content}
        )

    return examples if examples else None


def extract_all_examples(text):
    """
    Extracts all numbered examples along with their descriptions.
    """
    pattern = re.compile(
        r"(\d+\.\s+[A-Za-z0-9\s\-\,]+)\n(.*?)(?=\n\d+\.\s+[A-Za-z0-9\s\-\,]+|\Z)",
        re.DOTALL,
    )

    matches = pattern.findall(text)

    examples = {}
    for match in matches:
        title = match[0].strip()
        description = match[1].strip()
        examples[title] = description

    return examples


# region sector classification
def extract_classify_num_patents_w_experiments_w_subclass(
    folder_path="D:\\unzipped_patents_23_24",
):
    # https://dimensions.freshdesk.com/support/solutions/articles/23000018832-what-are-the-ipcr-and-cpc-patent-classifications- (IPCR AND CPC CLASSIFICATIONS)

    ipc_dic = extract_ipc_dic()
    subclass_dict = {}

    file_names = os.listdir(folder_path)
    total_num_of_patents = 0
    for i, file in enumerate(file_names):
        all_xml_parts = []
        if file.endswith(".xml"):
            print(f"Processing {file}... ({i + 1}/{len(file_names)})")
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
                    parts = [p for p in parts if p.strip()]
                    all_xml_parts.extend(parts)
            except Exception as e:
                print(f"Error processing {file}: {str(e)}")
            # xml_no_dup = remove_duplicate_docs(all_xml_parts)
            # print(f"Num of duplicates removed: {len(all_xml_parts) - len(xml_no_dup)} out of {len(all_xml_parts)}")
            total_num_of_patents += len(all_xml_parts)
            for j, xml in enumerate(all_xml_parts):
                if j % 2000 == 0:
                    print(f"Processing {j}/{len(all_xml_parts)}")
                root = etree.fromstring(xml.encode(), etree.XMLParser(recover=True))
                try:
                    sections = root.xpath(
                        "//classifications-ipcr/classification-ipcr/section"
                    )
                    classes = root.xpath(
                        "//classifications-ipcr/classification-ipcr/class"
                    )

                    # Get unique subclass names for this patent
                    this_subclass_names = set()
                    for section_elem, class_elem in zip(sections, classes):
                        section = section_elem.text
                        class_code = class_elem.text
                        full_code = section + class_code

                        try:
                            subclass_name = ipc_dic[section][full_code]
                            this_subclass_names.add(subclass_name)
                        except KeyError:
                            continue

                    # Update counts for each subclass found
                    for subclass_name in this_subclass_names:
                        if subclass_name not in subclass_dict:
                            subclass_dict[subclass_name] = {
                                "with_examples": 0,
                                "without_examples": 0,
                            }

                        if extract_experiments_w_heading(xml):
                            subclass_dict[subclass_name]["with_examples"] += (
                                1  # Fixed key name
                            )
                        else:
                            subclass_dict[subclass_name]["without_examples"] += 1

                except IndexError:
                    continue
            if i == 0:
                try:
                    start = file_names[i].split("a")[1].split(".")[0]
                    end = start
                except (IndexError, AttributeError):
                    # Fallback if file naming is inconsistent
                    start = str(i)
                    end = start
            else:
                try:
                    end = file_names[i].split("a")[1].split(".")[0]
                except (IndexError, AttributeError):
                    end = str(i)

            save_as_json(
                subclass_dict,
                f"subclass_of_{total_num_of_patents}_Patents_{start}_{end}.json",
            )

    return subclass_dict
