import nltk
from nltk import pos_tag, word_tokenize
from bs4 import BeautifulSoup
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")
nltk.download('punkt_tab')
nltk.download("averaged_perceptron_tagger_eng")
# region tense analysis


def analyze_sentence_tense(text, threshold=0.5):
    text = text.replace("  ", "").replace("\n", " ").replace("\t", " ")

    # Ensure required NLTK data is available
    try:
        nltk.data.find("taggers/averaged_perceptron_tagger")
    except LookupError:
        nltk.download("averaged_perceptron_tagger")
        nltk.download("punkt")

    # Tokenize and POS tag the text
    tokens = word_tokenize(text)
    tagged = pos_tag(tokens)

    verb_tenses = []
    reason_unknown = ""

    text_lower = text.lower()

    # Helper function to check for auxiliary/modal verbs
    def has_auxiliary(aux_list):
        return any(aux in text_lower for aux in aux_list)

    # Iterate through words with their POS tags
    for i, (word, tag) in enumerate(tagged):
        if tag.startswith("VB"):  # Checking for verb forms
            # Present Continuous: "is/are + VBG"
            if tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["is", "are"]:
                verb_tenses.append("present")  ####

            # Past Continuous: "was/were + VBG"
            elif tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["was", "were"]:
                verb_tenses.append("present")

            # Future Continuous: "will be + VBG"
            elif (
                tag == "VBG"
                and i > 1
                and tagged[i - 2][0].lower() == "will"
                and tagged[i - 1][0].lower() == "be"
            ):
                verb_tenses.append("present")

            # "Going to" Future: "am/is/are going to + VB"
            elif (
                word.lower() == "going"
                and i < len(tagged) - 1
                and tagged[i + 1][0].lower() == "to"
            ):
                verb_tenses.append("present")

            # Future Simple: "will + VB"
            elif i > 0 and tagged[i - 1][0].lower() == "will":
                verb_tenses.append("present")

            # Past Simple: "baked", "traveled" (VBD)
            elif tag == "VBD":
                verb_tenses.append("past")

            # Present Simple: "walks", "runs", "eats" (VBP, VBZ)
            elif tag in ["VBP", "VBZ"]:
                verb_tenses.append("present")

            # Past Participle: "was analyzed"
            elif tag == "VBN" and has_auxiliary(["was", "were"]):
                verb_tenses.append("past")

            # Present Perfect: "has analyzed"
            elif tag == "VBN" and has_auxiliary(["has", "have"]):
                verb_tenses.append("present")

            # Future Perfect: "will have analyzed"
            elif tag == "VBN" and has_auxiliary(["will have"]):
                verb_tenses.append("present")

    # If no tenses were found, return "unknown" with reason
    if not verb_tenses:
        reason_unknown = "no_verbs_found"
        return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

    # Use Counter to determine the most common tense
    tense_counts = Counter(verb_tenses)
    try:
        primary_tense = tense_counts.most_common(1)[0][0]
    except IndexError:
        reason_unknown = "no_primary_tense"
        return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

    # Confidence calculation
    total_verbs = sum(tense_counts.values())
    if total_verbs == 0:
        reason_unknown = "no_verbs_counted"
        return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

    # Calculate percentage breakdown of tenses
    tense_percentages = {
        tense: (count / total_verbs) * 100 for tense, count in tense_counts.items()
    }

    # Format breakdown string
    breakdown_str = ", ".join(
        [f"{tense}: {percent:.0f}%" for tense, percent in tense_percentages.items()]
    )

    # If there are multiple tenses with significant presence, consider it mixed
    has_mixed_tenses = (
        len([t for t, c in tense_counts.items() if c / total_verbs > 0.2]) > 1
    )

    return {
        "tense": primary_tense.lower(),
        "reason": "",
        "breakdown": tense_percentages,
        "breakdown_str": breakdown_str,
        "has_mixed": has_mixed_tenses,
    }


def check_tense_nltk(sentence):
    words = word_tokenize(sentence)
    tagged = pos_tag(words)

    past = ["VBD", "VBN"]
    present = ["VB", "VBG", "VBP", "VBZ", "MD"]

    tenses = {"past": 0, "present": 0}

    for word, tag in tagged:
        if tag in past:
            tenses["past"] += 1
        elif tag in present:
            tenses["present"] += 1
        elif word.lower() in ["will", "shall"]:
            tenses["present"] += 1

    return max(tenses, key=tenses.get) if max(tenses.values()) > 0 else "Unknown"


def process_text_for_tense(input_tuple):
    """Process a text tuple for tense analysis, suitable for multiprocessing."""
    idx, text = input_tuple
    return (idx, analyze_sentence_tense(text))


def dic_to_dic_w_tense_test(doc_w_exp, threshold=0):
    """Process patent examples with parallel tense analysis and track mixed tense data."""
    dic = {}
    # pattern = r"\(\d+\)\s*([A-Za-z0-9\-\(\)\{\},:;=\[\]\+\*\s\.\^\$\%]+(?:\.(?:sup|delta|Hz|NMR)[^\)]*)?)"

    # Calculate optimal workers for classification
    optimal_workers = max(
        1, (multiprocessing.cpu_count() * 3) // 4
    )  # Use 75% of CPU cores

    # Use ProcessPoolExecutor with increased workers for parallel tense analysis
    with ProcessPoolExecutor(max_workers=optimal_workers) as executor:
        for key, value in doc_w_exp.items():
            tense_counts = {"past": 0, "present": 0, "unknown": 0}
            mixed_tense_count = 0
            total_examples = 0

            if isinstance(value, list):
                # Add tense info to examples
                for example in value:
                    desc = example["title"] + "." + "".join(example["content"])
                    if len(desc) > threshold:
                        total_examples += 1

                # Prepare all texts for parallel processing
                texts_to_analyze = []
                for i, example in enumerate(value):
                    desc = example["title"] + "." + "".join(example["content"])
                    if len(desc) > threshold:
                        texts_to_analyze.append((i, desc))

                # Process all texts in parallel
                if texts_to_analyze:
                    # Use the standalone function instead of lambda
                    results = list(
                        executor.map(process_text_for_tense, texts_to_analyze)
                    )

                    # Aggregate results and update examples with tense details
                    for idx, tense_info in results:
                        example = value[idx]

                        # Get tense from result
                        tense = tense_info["tense"]

                        # Store tense analysis details in the example
                        example["tense"] = tense

                        # Make sure to properly set the reason for unknown tenses
                        if tense == "unknown":
                            example["why_unknown"] = tense_info.get(
                                "reason", "no_reason_provided"
                            )
                        else:
                            example["why_unknown"] = (
                                ""  # Clear field for non-unknown tenses
                            )

                        example["tense_breakdown"] = tense_info.get("breakdown_str", "")

                        # Track if this example has mixed tenses
                        has_mixed = tense_info.get("has_mixed", False)
                        if has_mixed:
                            mixed_tense_count += 1

                        tense_counts[tense] += 1

                    mixed_tense_percentage = (
                        (mixed_tense_count / total_examples * 100)
                        if total_examples > 0
                        else 0
                    )

                    # Add mixed tense percentage to the stats
                    tense_counts["mixed_tense_percentage"] = (
                        f"{round(mixed_tense_percentage)}%"
                    )

                    dic[key] = tense_counts

    return dic


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
    text = BeautifulSoup(text, "xml").get_text()

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
