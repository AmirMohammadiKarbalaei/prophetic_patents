import re
from bs4 import BeautifulSoup
from lxml import etree
import json
from collections import defaultdict
import os
import requests


def save_as_json(examples, filename="1200_patents_w_experiments.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=4, ensure_ascii=False)
    print(f"Saved as {filename}")


def extract_num_dot_examples(text):
    soup = BeautifulSoup(text, "html.parser")

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
    soup = BeautifulSoup(text, "html.parser")

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


"""7824"""
# def extract_experiments_w_heading(text):
#     """Extracts the 'Examples' section and its experiments from a patent text."""

#     # Use BeautifulSoup to parse the structure (for HTML-like patents)
#     soup = BeautifulSoup(text, "html.parser")

#     # Find the "EXAMPLES" section heading
#     examples_heading = soup.find(
#         lambda tag: tag.name == "heading"
#         and (
#             "EXAMPLES" in tag.text.upper()
#             or "EXAMPLE" == tag.text.upper()
#             or "EXPERIMENT" == tag.text.upper()
#             or "EXPERIMENTS" in tag.text.upper()
#         )
#     )
#     if not examples_heading:
#         # print("No 'Examples' section found.")
#         return None

#     # Extract everything after the 'EXAMPLES' heading until the next major section
#     # experiments = []
#     # for sibling in examples_heading.find_next_siblings():
#     #     if (
#     #         sibling.name == "heading" and sibling["level"] == "1"
#     #     ):  # Stop at the next main section
#     #         break
#     #     experiments.append(sibling.text)

#     return examples_heading  # "\n".join(experiments)


def extract_examples_start_w_word(siblings):
    """
    Extracts examples/experiments/tests sections that start with specific words (example, experiment, test) from the given xml siblings.

    Args:
        siblings (list): List of sibling tags to process.

    Returns:
        list: List of dictionaries containing the extracted examples.
    """
    examples = []
    current_example = None
    in_example = False

    for tag in siblings:
        if tag.name == "heading":
            if (
                tag.text.strip().lower().startswith("example")
                or tag.text.strip().lower().startswith("experiment")
                or tag.text.strip().lower().startswith("test")
            ):
                in_example = True
                current_example = {
                    "number": tag.text.strip(),
                    "title": siblings[siblings.index(tag) + 1].text.strip(),
                    "content": [],
                }
                examples.append(current_example)
            else:
                # If we hit any other heading, stop collecting content
                in_example = False
        elif in_example and tag.name == "p" and current_example is not None:
            current_example["content"].append(tag.text.strip())

    return examples


def extract_examples_w_word(text):
    """Extract examples/experiments/tests sections from a patent text by looking for specific keywords in headings and
    extarcxting the content until the next heading with specific keywords is found.

    Args:
        text (str): The patent text to extract examples from.

    Returns:
        list: A list of dictionaries containing the extracted examples."""

    soup = BeautifulSoup(text, "html.parser")
    examples = []

    example_headings = soup.findAll(
        lambda tag: tag.name == "heading"
        and any(
            keyword in tag.text.strip().lower()
            for keyword in ["example", "experiment", "test"]
        )
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
        ):
            if sibling.name == "p":
                current_content.append(sibling.text.strip())
            sibling = sibling.find_next_sibling()

        examples.append(
            {"number": heading.text.strip(), "title": title, "content": current_content}
        )

    return examples if examples else None


def process_siblings(siblings):
    examples = []

    # Find all matching headings directly from siblings
    example_headings = [
        tag
        for tag in siblings
        if tag.name == "heading"
        and any(
            keyword in tag.text.strip().lower().replace(" ", "")
            for keyword in ["example", "experiment", "test"]
        )
    ]

    for heading in example_headings:
        current_content = []
        idx = siblings.index(heading)

        # Get title from next heading if available
        title = ""
        if idx + 1 < len(siblings) and siblings[idx + 1].name == "heading":
            title = siblings[idx + 1].text.strip()

        # Collect content until next example heading
        i = idx + 1
        while i < len(siblings):
            if siblings[i].name == "heading" and any(
                keyword in siblings[i].text.strip().lower()
                for keyword in ["example", "experiment", "test"]
            ):
                break
            if siblings[i].name == "p":
                current_content.append(siblings[i].text.strip())
            i += 1

        examples.append(
            {"number": heading.text.strip(), "title": title, "content": current_content}
        )

    return examples if examples else None


# Test the function
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


def clean_text(text):
    """
    Clean text by removing special characters, extra spaces, and normalizing content

    Args:
        text (str): Input text to clean

    Returns:
        str: Cleaned text
    """
    if not isinstance(text, str):
        return ""

    # Remove HTML tags if present
    text = BeautifulSoup(text, "html.parser").get_text()

    # Replace newlines, tabs, and multiple spaces
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\n\t\r]", " ", text)

    # Remove special characters but keep important punctuation
    text = re.sub(r"[^a-zA-Z0-9\s\.\,\?\!\-\']", "", text)

    # Remove extra spaces around punctuation
    text = re.sub(r"\s*([\.!?,])\s*", r"\1 ", text)

    # Remove multiple spaces and strip
    text = " ".join(text.split())

    return text.strip()


def find_doc_number(xml_part):
    root = etree.fromstring(xml_part.encode(), etree.XMLParser(recover=True))
    doc_num = root.xpath("//publication-reference//document-id//doc-number/text()")
    return doc_num


def find_patent_number(xml_part):
    root = etree.fromstring(xml_part.encode(), etree.XMLParser(recover=True))
    patent_num = root.xpath("//application-reference//document-id//doc-number/text()")
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


# def find_doc_number(xml_part):
#     parser = etree.XMLParser(recover=True)
#     root = etree.fromstring(xml_part.encode(), parser)
#     doc_num = root.xpath("//publication-reference//document-id//doc-number/text()")
#     return doc_num
# def remove_duplicate_docs(xml_parts):
#     """
#     Remove duplicate documents keeping only the longest version.

#     Args:
#         xml_parts (list): List of XML documents

#     Returns:
#         list: XML documents with duplicates removed
#     """
#     # Create dictionaries to store document numbers and details
#     doc_versions = defaultdict(list)
#     doc_lengths = {}

#     # Collect all document numbers with positions and lengths
#     for i, xml in enumerate(xml_parts[1:], start=1):
#         doc_num = find_doc_number(xml)[0]
#         doc_versions[doc_num].append(i)
#         doc_lengths[i] = len(xml)

#     # Find documents with multiple versions
#     duplicate_docs = {
#         doc_num: positions
#         for doc_num, positions in doc_versions.items()
#         if len(positions) > 1
#     }

#     # Remove shorter versions
#     indices_to_remove = []
#     for doc_num, positions in duplicate_docs.items():
#         longest_pos = max(positions, key=lambda pos: doc_lengths[pos])
#         indices_to_remove.extend([pos for pos in positions if pos != longest_pos])

#     # Sort indices in reverse order to remove from end first
#     indices_to_remove.sort(reverse=True)

#     # Create new list without duplicates
#     cleaned_parts = xml_parts.copy()
#     for idx in indices_to_remove:
#         cleaned_parts.pop(idx)

#     return cleaned_parts


def download_files(main_url, download_path, files):
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    for index, file_name in enumerate(files):
        url = main_url + file_name

        zip_file_path = os.path.join(download_path, file_name)  # .split(".")[-1]
        response = requests.get(url, stream=True, timeout=10)
        with open(zip_file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded {file_name} ------- {index + 1} / {len(files)}")


def fetch_urls_from_pto(start_year, end_year):
    urls = {}
    if start_year > end_year:
        for year in range(start_year, end_year + 1):
            url = f"https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/{year}/"
            rp = requests.get(url, timeout=10)
            root = etree.fromstring(rp.text.encode(), etree.XMLParser(recover=True))
            href_values = root.findall(".//a[@href]")
            urls[year] = [
                href.get("href")
                for href in href_values
                if href.get("href").endswith(".zip")
            ]
    elif start_year == end_year:
        url = f"https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/{start_year}/"
        rp = requests.get(url, timeout=10)
        root = etree.fromstring(rp.text.encode(), etree.XMLParser(recover=True))
        href_values = root.findall(".//a[@href]")
        urls[start_year] = [
            href.get("href")
            for href in href_values
            if href.get("href").endswith(".zip")
        ]

    return urls


def get_latest_versions(urls):
    """
    Function to extract the latest versions of files based on a regex pattern.

    Args:
    - urls (dict): A dictionary where keys are years and values are lists of filenames.

    Returns:
    - latest_files (dict): A dictionary where keys are years and values are lists of the latest versions of the files for that year.
    """
    # Initialize the result dictionary to store the latest versions for each year
    latest_files = {}

    # Regex to extract date and optional revision number
    pattern = re.compile(r"(ipa\d{6})(?:_r(\d+))?\.zip")

    # Process each year in the input dictionary
    for year in urls.keys():
        latest_versions = {}  # Holds the latest version of files for the current year
        for file in urls[year]:
            match = pattern.match(file)
            if match:
                base_name, revision = match.groups()
                revision = (
                    int(revision) if revision else 0
                )  # Default to 0 if no revision

                # Extract the current highest revision number for the base_name
                current_revision_match = re.search(
                    r"_r(\d+)", latest_versions.get(base_name, "")
                )
                current_revision = (
                    int(current_revision_match.group(1))
                    if current_revision_match
                    else 0
                )

                # Update if the new file has a higher revision
                if base_name not in latest_versions or revision > current_revision:
                    latest_versions[base_name] = file

        # Get the final list of unique latest versions sorted by file name
        latest_files[year] = sorted(latest_versions.values())

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


def extract_ipc_dic(ipc_path="./EN_ipc_title_list_20250101"):
    ipc_path = "./EN_ipc_title_list_20250101"
    file_names = os.listdir(ipc_path)
    ipc_dict = {}
    for file_name in file_names:
        with open(ipc_path + "/" + file_name, "r", encoding="utf-8") as file:
            lines = file.readlines()  # each line becomes an element in a list
            lines = [line.strip() for line in lines]
        dic = {l.split("\t")[0]: l.split("\t")[1] for l in lines[1:] if "\t" in l[:4]}
        ipc_dict[file_name.split("_")[3]] = dic
    return ipc_dict


def extract_classify_num_patents_w_experiments_w_subclass(
    folder_path="D:\\unzipped_patents_23_24",
):
    # https://dimensions.freshdesk.com/support/solutions/articles/23000018832-what-are-the-ipcr-and-cpc-patent-classifications- (IPCR AND CPC CLASSIFICATIONS)

    ipc_dic = extract_ipc_dic()
    subclass_dict = {}

    file_names = os.listdir(folder_path)
    total_num_of_patents = 0
    for i, file_name in enumerate(file_names):
        all_xml_parts = []
        if file_name.endswith(".xml"):
            print(f"Processing {file_name}... ({i + 1}/{len(file_names)})")
            file_path = os.path.join(folder_path, file_name)
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
                            subclass_dict[subclass_name]["with_examples"] += 1
                        else:
                            subclass_dict[subclass_name]["without_examples"] += 1

                except IndexError:
                    continue
            if i == 0:
                start = file_name.split("a")[1].split(".")[0]
                end = start
            else:
                end = file_name.split("a")[1].split(".")[0]

            save_as_json(
                subclass_dict,
                f"subclass_of_{total_num_of_patents}_Patents_{start}_{end}.json",
            )

    return subclass_dict
