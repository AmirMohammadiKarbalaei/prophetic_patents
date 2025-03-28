import nltk
from nltk import pos_tag, word_tokenize
from bs4 import BeautifulSoup
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")
nltk.download('averaged_perceptron_tagger_eng')
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

    # Time indicators (adverbs, phrases)
    # future_time = {'tomorrow', 'soon', 'later', 'in the future'}
    # past_time = {'yesterday', 'last', 'ago', 'previously', 'earlier'}
    # present_time = {'now', 'currently', 'at the moment', 'as we speak'}

    # Check for time-related words
    text_lower = text.lower()
    # if any(word in text_lower for word in future_time):
    #     verb_tenses.append('Future')
    # if any(word in text_lower for word in past_time):
    #     verb_tenses.append('Past')
    # if any(word in text_lower for word in present_time):
    #     verb_tenses.append('Present')
    # if "was" in text_lower or "were" in text_lower:
    #     return "past"

    # Helper function to check for auxiliary/modal verbs
    def has_auxiliary(aux_list):
        return any(aux in text_lower for aux in aux_list)

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
    # if not verb_tenses:
    #     return "past"

    # Use Counter to determine the most common tense
    tense_counts = Counter(verb_tenses)
    try:
        primary_tense = tense_counts.most_common(1)[0][0]
    except IndexError:
        return "unknown"

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


def dic_to_dic_w_tense_test(doc_w_exp, threshold=0):
    """Process patent examples with parallel tense analysis."""
    dic = {}
    pattern = r"\(\d+\)\s*([A-Za-z0-9\-\(\)\{\},:;=\[\]\+\*\s\.\^\$\%]+(?:\.(?:sup|delta|Hz|NMR)[^\)]*)?)"

    # Calculate optimal workers for classification (use more CPU cores)
    optimal_workers = max(
        1, (multiprocessing.cpu_count() * 3) // 4
    )  # Use 75% of CPU cores

    # Use ProcessPoolExecutor with increased workers for parallel tense analysis
    with ProcessPoolExecutor(max_workers=optimal_workers) as executor:
        for key, value in doc_w_exp.items():
            tense_counts = {"past": 0, "present": 0, "unknown": 0}

            if isinstance(value, list):
                # Prepare all texts for parallel processing
                texts_to_analyze = []
                for example in value:
                    desc = example["title"] + "." + "".join(example["content"])
                    if len(desc) > threshold:
                        texts_to_analyze.append(desc)

                # Process all texts in parallel
                if texts_to_analyze:
                    results = list(
                        executor.map(analyze_sentence_tense, texts_to_analyze)
                    )

                    # Aggregate results
                    for i, tense in enumerate(results):
                        if tense != "unknown":
                            tense_counts[tense] += 1
                        else:
                            # Check for number patterns in unknown cases
                            matches = re.findall(pattern, texts_to_analyze[i])
                            if matches:
                                tense_counts["past"] += 1
                            else:
                                tense_counts["unknown"] += 1

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
