import nltk
from nltk import pos_tag, word_tokenize
from bs4 import BeautifulSoup
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")
nltk.download("punkt_tab")
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

    # Check for time-related words
    text_lower = text.lower()
    # if any(word in text_lower for word in future_time):
    #     verb_tenses.append('Future')
    # if any(word in text_lower for word in past_time):
    #     verb_tenses.append('Past')
    # if any(word in text_lower for word in present_time):
    #     verb_tenses.append('Present')
    if "was" in text_lower or "were" in text_lower:
        return "past"

    # if text.strip().startswith(('Prepared', 'Obtained', 'Synthesized', 'Isolated')):
    #     return "past"
    def has_passive_voice(tagged):
        """Check if sentence contains passive voice construction"""
        for i, (word, tag) in enumerate(tagged):
            # Check for past participle
            if tag == "VBN":
                # Look for forms of "be" verb before it
                if i > 0 and tagged[i - 1][0].lower() in [
                    "was",
                    "were",
                    "is",
                    "are",
                    "be",
                ]:
                    return True
                # Check if VBN starts the sentence (implied passive)
                if i == 0:
                    return True
        return False

    def is_patent_procedure(text, tagged):
        """Check if text matches patent procedure patterns"""
        # Common patent procedure starters
        procedure_starters = {
            "prepared",
            "obtained",
            "synthesized",
            "isolated",
            "dissolved",
            "mixed",
            "combined",
            "heated",
            "cooled",
            "filtered",
            "purified",
            "separated",
        }

        # Check if starts with procedure word
        first_word = text.strip().split()[0].lower()
        if first_word in procedure_starters:
            return True

        # Check for chemical procedure patterns
        procedure_patterns = [
            "according to",
            "following the procedure",
            "as described",
            "using the method",
            "following example",
        ]
        if any(pattern in text.lower() for pattern in procedure_patterns):
            return True

        return False

    # Helper function to check for auxiliary/modal verbs
    def has_auxiliary(aux_list):
        return any(aux in text_lower for aux in aux_list)

    if has_passive_voice(tagged):
        return "past"
    if is_patent_procedure(text, tagged):
        return "past"

    # Iterate through words with their POS tags
    for i, (word, tag) in enumerate(tagged):
        if tag.startswith("VB"):  # Checking for verb forms
            # Present Continuous: "is/are + VBG"
            if tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["is", "are"]:
                verb_tenses.append("Present")  ####

            # Past Continuous: "was/were + VBG"
            elif tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["was", "were"]:
                verb_tenses.append("Present")

            # Future Continuous: "will be + VBG"
            elif (
                tag == "VBG"
                and i > 1
                and tagged[i - 2][0].lower() == "will"
                and tagged[i - 1][0].lower() == "be"
            ):
                verb_tenses.append("Present")

            # "Going to" Future: "am/is/are going to + VB"
            elif (
                word.lower() == "going"
                and i < len(tagged) - 1
                and tagged[i + 1][0].lower() == "to"
            ):
                verb_tenses.append("Present")

            # Future Simple: "will + VB"
            elif i > 0 and tagged[i - 1][0].lower() == "will":
                verb_tenses.append("present")

            # Past Simple: "baked", "traveled" (VBD)
            elif tag == "VBD":
                verb_tenses.append("Past")

            # Present Simple: "walks", "runs", "eats" (VBP, VBZ)
            elif tag in ["VBP", "VBZ"]:
                verb_tenses.append("Present")

            # Past Participle: "was analyzed"
            elif tag == "VBN" and has_auxiliary(["was", "were"]):
                verb_tenses.append("Past")

            # Present Perfect: "has analyzed"
            elif tag == "VBN" and has_auxiliary(["has", "have"]):
                verb_tenses.append("Present")

            # Future Perfect: "will have analyzed"
            elif tag == "VBN" and has_auxiliary(["will have"]):
                verb_tenses.append("Present")

    # If no tenses were found, return "unknown"
    if not verb_tenses:
        print(tagged)
        return "unknown"

    # Use Counter to determine the most common tense
    tense_counts = Counter(verb_tenses)
    primary_tense = tense_counts.most_common(1)[0][0]

    # Confidence calculation
    total_verbs = sum(tense_counts.values())
    # confidence = tense_counts.most_common(1)[0][1] / total_verbs
    if total_verbs == 0:
        return "unknown"
    # if total_verbs<10:
    #     print(primary_tense)
    #     print(text)

    # If confidence is too low, return "unknown"
    # if confidence < threshold:
    #     # print(primary_tense)
    #     # print(text)

    #     return "past"

    return primary_tense.lower()


# def analyze_sentence_tense(text, threshold=0.5):
#     text = text.replace("  ", "").replace("\n", " ").replace("\t", " ")

#     # Ensure required NLTK data is available
#     try:
#         nltk.data.find("taggers/averaged_perceptron_tagger")
#     except LookupError:
#         nltk.download("averaged_perceptron_tagger")
#         nltk.download("punkt")

#     # Tokenize and POS tag the text
#     tokens = word_tokenize(text)
#     tagged = pos_tag(tokens)

#     verb_tenses = []
#     reason_unknown = ""

#     text_lower = text.lower()

#     # Helper function to check for auxiliary/modal verbs
#     def has_auxiliary(aux_list):
#         return any(aux in text_lower for aux in aux_list)

#     # Iterate through words with their POS tags
#     for i, (word, tag) in enumerate(tagged):
#         if tag.startswith("VB"):  # Checking for verb forms
#             # Present Continuous: "is/are + VBG"
#             if tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["is", "are"]:
#                 verb_tenses.append("present")  ####

#             # Past Continuous: "was/were + VBG"
#             elif tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["was", "were"]:
#                 verb_tenses.append("present")

#             # Future Continuous: "will be + VBG"
#             elif (
#                 tag == "VBG"
#                 and i > 1
#                 and tagged[i - 2][0].lower() == "will"
#                 and tagged[i - 1][0].lower() == "be"
#             ):
#                 verb_tenses.append("present")

#             # "Going to" Future: "am/is/are going to + VB"
#             elif (
#                 word.lower() == "going"
#                 and i < len(tagged) - 1
#                 and tagged[i + 1][0].lower() == "to"
#             ):
#                 verb_tenses.append("present")

#             # Future Simple: "will + VB"
#             elif i > 0 and tagged[i - 1][0].lower() == "will":
#                 verb_tenses.append("present")

#             # Past Simple: "baked", "traveled" (VBD)
#             elif tag == "VBD":
#                 verb_tenses.append("past")

#             # Present Simple: "walks", "runs", "eats" (VBP, VBZ)
#             elif tag in ["VBP", "VBZ"]:
#                 verb_tenses.append("present")

#             # Past Participle: "was analyzed"
#             elif tag == "VBN" and has_auxiliary(["was", "were"]):
#                 verb_tenses.append("past")

#             # Present Perfect: "has analyzed"
#             elif tag == "VBN" and has_auxiliary(["has", "have"]):
#                 verb_tenses.append("present")

#             # Future Perfect: "will have analyzed"
#             elif tag == "VBN" and has_auxiliary(["will have"]):
#                 verb_tenses.append("present")

#     # If no tenses were found, return "unknown" with reason
#     if not verb_tenses:
#         reason_unknown = "no_verbs_found"
#         return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

#     # Use Counter to determine the most common tense
#     tense_counts = Counter(verb_tenses)
#     try:
#         primary_tense = tense_counts.most_common(1)[0][0]
#     except IndexError:
#         reason_unknown = "no_primary_tense"
#         return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

#     # Confidence calculation
#     total_verbs = sum(tense_counts.values())
#     if total_verbs == 0:
#         reason_unknown = "no_verbs_counted"
#         return {"tense": "unknown", "reason": reason_unknown, "breakdown": {}}

#     # Calculate percentage breakdown of tenses
#     tense_percentages = {
#         tense: (count / total_verbs) * 100 for tense, count in tense_counts.items()
#     }

#     # Format breakdown string
#     breakdown_str = ", ".join(
#         [f"{tense}: {percent:.0f}%" for tense, percent in tense_percentages.items()]
#     )

#     # If there are multiple tenses with significant presence, consider it mixed
#     has_mixed_tenses = (
#         len([t for t, c in tense_counts.items() if c / total_verbs > 0.2]) > 1
#     )

#     return {
#         "tense": primary_tense.lower(),
#         "reason": "",
#         "breakdown": tense_percentages,
#         "breakdown_str": breakdown_str,
#         "has_mixed": has_mixed_tenses,
#     }


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


def safe_join(content_list):
    """Safely join content lists, handling both list and string inputs."""
    if isinstance(content_list, list):
        return " ".join(str(item) for item in content_list)
    elif isinstance(content_list, str):
        return content_list
    return ""


def dic_to_dic_w_tense_test(doc_w_exp, threshold=0):
    """Process patent examples with parallel tense analysis and track mixed tense data."""
    dic = {}
    optimal_workers = max(1, (multiprocessing.cpu_count() * 3) // 4)

    with ProcessPoolExecutor(max_workers=optimal_workers) as executor:
        for key, value in doc_w_exp.items():
            tense_counts = {"past": 0, "present": 0, "unknown": 0}
            mixed_tense_count = 0
            total_examples = 0

            if isinstance(value, list):
                for example in value:
                    if not isinstance(example, dict):
                        continue

                    title = example.get("title", "")
                    content = example.get("content", [])
                    desc = title + "." + safe_join(content)

                    if len(desc) > threshold:
                        total_examples += 1

                texts_to_analyze = []
                for i, example in enumerate(value):
                    if not isinstance(example, dict):
                        continue

                    title = example.get("title", "")
                    content = example.get("content", [])
                    desc = title + "." + safe_join(content)

                    if len(desc) > threshold:
                        texts_to_analyze.append((i, desc))

                if texts_to_analyze:
                    results = list(
                        executor.map(process_text_for_tense, texts_to_analyze)
                    )

                    for idx, tense in results:
                        if idx >= len(value):
                            continue

                        example = value[idx]
                        if not isinstance(example, dict):
                            continue

                        tense_counts[tense] += 1
                        example["tense"] = tense

            if total_examples > 0:
                dic[key] = tense_counts
                mixed_tense_percentage = mixed_tense_count / total_examples * 100
                dic[key]["mixed_tense_percentage"] = f"{round(mixed_tense_percentage)}%"

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
