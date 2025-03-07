import nltk
from nltk import pos_tag, word_tokenize
from bs4 import BeautifulSoup
import re


nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")


# region tense analysis
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


# region NLP Processing
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
