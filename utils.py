import re
from bs4 import BeautifulSoup
from lxml import etree
import json
from collections import defaultdict


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
        and any(
            keyword in tag.text.upper().replace(" ", "")
            for keyword in [
                "EXAMPLES",
                # "EXAMPLE",
                # "EXPERIMENT",
                "EXPERIMENTS",
                "Tests",
            ]
        )
    )

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
    """Find all example/experiment/test sections and extract their content"""
    soup = BeautifulSoup(text, "html.parser")
    examples = []

    # Find all matching headings
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


def find_doc_number(xml_part):
    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(xml_part.encode(), parser)
    doc_num = root.xpath("//publication-reference//document-id//doc-number/text()")
    return doc_num


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


def remove_duplicate_docs(xml_parts):
    """
    Remove duplicate documents keeping only the longest version.

    Args:
        xml_parts (list): List of XML documents

    Returns:
        list: XML documents with duplicates removed
    """
    # Create dictionaries to store document numbers and details
    doc_versions = defaultdict(list)
    doc_lengths = {}

    # Collect all document numbers with positions and lengths
    for i, xml in enumerate(xml_parts[1:], start=1):
        doc_num = find_doc_number(xml)[0]
        doc_versions[doc_num].append(i)
        doc_lengths[i] = len(xml)

    # Find documents with multiple versions
    duplicate_docs = {
        doc_num: positions
        for doc_num, positions in doc_versions.items()
        if len(positions) > 1
    }

    # Remove shorter versions
    indices_to_remove = []
    for doc_num, positions in duplicate_docs.items():
        longest_pos = max(positions, key=lambda pos: doc_lengths[pos])
        indices_to_remove.extend([pos for pos in positions if pos != longest_pos])

    # Sort indices in reverse order to remove from end first
    indices_to_remove.sort(reverse=True)

    # Create new list without duplicates
    cleaned_parts = xml_parts.copy()
    for idx in indices_to_remove:
        cleaned_parts.pop(idx)

    return cleaned_parts
