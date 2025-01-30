import nltk
from nltk import pos_tag, word_tokenize
import re

nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")


from bs4 import BeautifulSoup


def extract_experiments_w_heading(text):
    """Extracts the 'Examples' section and its experiments from a patent text."""

    # Use BeautifulSoup to parse the structure (for HTML-like patents)
    soup = BeautifulSoup(text, "html.parser")

    # Find the "EXAMPLES" section heading
    examples_heading = soup.find(
        lambda tag: tag.name == "heading"
        and (
            "EXAMPLES" in tag.text.upper()
            or "EXAMPLE" in tag.text.upper()
            or "EXPERIMENT" in tag.text.upper()
            or "EXPERIMENTS" in tag.text.upper()
        )
    )
    if not examples_heading:
        # print("No 'Examples' section found.")
        return None

    # Extract everything after the 'EXAMPLES' heading until the next major section
    experiments = []
    for sibling in examples_heading.find_next_siblings():
        if (
            sibling.name == "heading" and sibling["level"] == "1"
        ):  # Stop at the next main section
            break
        experiments.append(sibling.text)

    return "\n".join(experiments)


def check_tense_nltk(sentence):
    words = word_tokenize(sentence)
    tagged = pos_tag(words)

    past = ["VBD", "VBN"]
    present = ["VB", "VBG", "VBP", "VBZ"]
    future = ["MD"]

    tenses = {"past": 0, "present": 0, "future": 0}

    for word, tag in tagged:
        if tag in past:
            tenses["past"] += 1
        elif tag in present:
            tenses["present"] += 1
        elif tag in future and word.lower() in ["will", "shall"]:
            tenses["future"] += 1

    return max(tenses, key=tenses.get) if max(tenses.values()) > 0 else "Unknown"


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
