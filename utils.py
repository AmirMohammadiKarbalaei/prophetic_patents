import re
from bs4 import BeautifulSoup
from lxml import etree


def extract_experiments_w_heading(text):
    """Extracts the 'Examples' section and its experiments from a patent text."""

    # Use BeautifulSoup to parse the structure (for HTML-like patents)
    soup = BeautifulSoup(text, "html.parser")

    # Find the "EXAMPLES" section heading
    examples_heading = soup.find(
        lambda tag: tag.name == "heading"
        and (
            "EXAMPLES" in tag.text.upper()
            or "EXAMPLE" == tag.text.upper()
            or "EXPERIMENT" == tag.text.upper()
            or "EXPERIMENTS" in tag.text.upper()
        )
    )
    if not examples_heading:
        # print("No 'Examples' section found.")
        return None

    # Extract everything after the 'EXAMPLES' heading until the next major section
    # experiments = []
    # for sibling in examples_heading.find_next_siblings():
    #     if (
    #         sibling.name == "heading" and sibling["level"] == "1"
    #     ):  # Stop at the next main section
    #         break
    #     experiments.append(sibling.text)

    return examples_heading  # "\n".join(experiments)


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
