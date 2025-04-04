from bs4 import BeautifulSoup
from lxml import etree
import re
import os


def remove_leadiong_zeros(s):
    s = s.replace("[", "").replace("]", "").replace("'", "").replace(" ", "")

    if len(s) == 8 and s.startswith("0"):
        s = s[1:]
    return s


def find_doc_number(xml_part):
    """Find document number with improved error handling."""
    try:
        root = etree.fromstring(xml_part.encode(), etree.XMLParser(recover=True))
        if root is None:
            return []

        doc_num = root.xpath("//publication-reference//document-id//doc-number/text()")
        return doc_num if doc_num else []
    except Exception:
        return []


def remove_duplicate_docs(xml_parts):
    """Remove duplicate documents with improved validation."""
    doc_versions = {}

    for xml in xml_parts:
        try:
            doc_nums = find_doc_number(xml)
            if not doc_nums:
                continue

            doc_num = doc_nums[0]
            if doc_num not in doc_versions or len(xml) > len(doc_versions[doc_num]):
                doc_versions[doc_num] = xml
        except Exception:
            continue

    return list(doc_versions.values())


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
            "EXPERIMENTS",
            "TESTS",
        ]
    )

    if not examples_headings:
        return None

    return examples_headings


def extract_examples_start_w_word_all(xml_siblings):
    examples = []
    current_example = None
    in_example = False

    for tag in xml_siblings:
        if tag.name == "heading":
            if (
                tag.text.strip().lower().startswith("example")
                or tag.text.strip().lower().startswith("experiment")
                or tag.text.strip().lower().startswith("test")
                or tag.text.strip().lower().startswith("trial")
                or "test" in tag.text.strip().lower()
                or "experiment" in tag.text.strip().lower()
                or "example" in tag.text.strip().lower()
                or "trial" in tag.text.strip().lower()
            ) and not any(
                tag.text.strip().lower().startswith("examples")
                or tag.text.strip().lower().startswith("experiments")
                or tag.text.strip().lower().startswith("tests")
                for tag in xml_siblings
            ):
                in_example = True
                current_example = {
                    "number": tag.text.strip(),
                    "title": xml_siblings[xml_siblings.index(tag) + 1].text.strip(),
                    "content": [],
                }
                examples.append(current_example)
        elif (
            tag.name == "heading"
            and tag.text.strip().lower() == "exampels"
            and (
                tag.text.strip().lower().startswith("example")
                or tag.text.strip().lower().startswith("experiment")
                or tag.text.strip().lower().startswith("test")
                or tag.text.strip().lower().startswith("trial")
                or "test" in tag.text.strip().lower()
                or "experiment" in tag.text.strip().lower()
                or "example" in tag.text.strip().lower()
                or "trial" in tag.text.strip().lower()
            )
            and not any(
                tag.text.strip().lower().startswith("examples")
                or tag.text.strip().lower().startswith("experiments")
                or tag.text.strip().lower().startswith("tests")
                for tag in xml_siblings
            )
        ):
            in_example = False
        elif in_example and current_example is not None:
            current_example["content"].append(tag.text.strip())

    return examples
