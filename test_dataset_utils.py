import os
import xml.etree.ElementTree as ET
from utils_clean import find_doc_number, read_xlsb_file, save_as_pickle


def remove_leadiong_zeros(s):
    s = s.replace("[", "").replace("]", "").replace("'", "").replace(" ", "")

    if len(s) == 8 and s.startswith("0"):
        s = s[1:]
    return s


def process_large_xml_filtered(file_path, target_doc_numbers, xml_dict):
    """
    Reads a large XML file and extracts full XML content for specific document numbers.

    Args:
        file_path: Path to XML files
        target_doc_numbers: List of document numbers we want to extract
        xml_dict: Dictionary to store results {doc_number: xml_content}
    """
    xml_buffer = ""
    inside_xml = False

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("<?xml"):  # Start of a new XML block
                if xml_buffer:  # Process previous buffer if exists
                    doc_num = remove_leadiong_zeros(find_doc_number(xml_buffer)[0])
                    if doc_num and doc_num in target_doc_numbers:
                        xml_dict[doc_num] = xml_buffer

                xml_buffer = line  # Start new XML buffer
                inside_xml = True
            elif inside_xml:
                xml_buffer += line  # Append line to current XML

        # Process last XML section
        if xml_buffer:
            doc_num = remove_leadiong_zeros(find_doc_number(xml_buffer)[0])
            if doc_num and doc_num in target_doc_numbers:
                xml_dict[doc_num] = xml_buffer


def find_doc_number_and_xml_content(path, target_doc_numbers):
    """
    Extracts full XML content for specified document numbers.

    Args:
        path: Directory containing XML files
        target_doc_numbers: List of document numbers to extract
    Returns:
        Dictionary mapping document numbers to their XML content
    """
    xml_dict = {}

    with os.scandir(path) as entries:
        for entry in entries:
            if entry.name.endswith(".xml") and entry.is_file():
                print(f"Processing {entry.name}")
                process_large_xml_filtered(entry.path, target_doc_numbers, xml_dict)

                # Early exit if we found all documents
                if len(xml_dict) == len(target_doc_numbers):
                    break

    print(f"Found {len(xml_dict)} out of {len(target_doc_numbers)} documents")
    return xml_dict


def create_test_dataset_from_freilich(
    year=2015,
    freilich_data_path="Freilich.Data.Compressed.xlsb",
    path_to_all_xmls_for_chosen_year="patent_grants_2015",
):
    # Read and prepare Freilich dataset
    df = read_xlsb_file(freilich_data_path)
    df_year = df[df.issueyear == year]
    df_year_doc_num_cleaned_freilich = [
        str(i).replace(".0", "") for i in df_year.patentnumber.values
    ]

    # Get XML content for matching documents
    test_dataset = find_doc_number_and_xml_content(
        path_to_all_xmls_for_chosen_year,
        set(df_year_doc_num_cleaned_freilich),  # Convert to set for faster lookups
    )

    # Save results
    save_as_pickle(test_dataset, f"test_dataset_{year}.pkl")
    return test_dataset


def clean_patent_number(x):
    try:
        # Remove any non-numeric characters and convert
        if isinstance(x, str):
            # Extract only numbers from string
            nums = "".join(filter(str.isdigit, x))
            return int(nums) if nums else 0
        elif isinstance(x, (int, float)):
            return int(x)
        return 0
    except (ValueError, TypeError):
        return 0
