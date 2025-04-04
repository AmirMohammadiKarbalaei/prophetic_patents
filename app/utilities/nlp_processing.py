import nltk
from nltk import pos_tag, word_tokenize
from bs4 import BeautifulSoup
from collections import Counter
import re
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("averaged_perceptron_tagger_eng")


def analyze_sentence_tense(text, threshold=0.5):
    """Analyze sentence tense with enhanced breakdown information."""
    text = text.replace("  ", "").replace("\n", " ").replace("\t", " ")

    verb_tenses = []
    tense_details = {"past": 0, "present": 0, "unknown": 0}
    why_unknown = ""

    # Early return for unknown cases
    if not text.strip():
        return {
            "tense": "unknown",
            "breakdown": tense_details,
            "breakdown_str": "",  # Empty for unknown
            "has_mixed": False,
            "percentages": {"past": 0, "present": 0, "unknown": 100},
            "why_unknown": "empty_text",
        }

    # Add direct past tense indicators
    text_lower = text.lower()
    if "was" in text_lower or "were" in text_lower:
        tense_details["past"] = 1
        total_verbs = 1
        return {
            "tense": "past",
            "breakdown": tense_details,
            "breakdown_str": "past: 100%",
            "has_mixed": False,
            "percentages": {"past": 100, "present": 0, "unknown": 0},
            "why_unknown": "",
        }

    def has_passive_voice(tagged):
        """Check if sentence contains passive voice construction"""
        for i, (word, tag) in enumerate(tagged):
            if tag == "VBN":
                if i > 0 and tagged[i - 1][0].lower() in [
                    "was",
                    "were",
                    "is",
                    "are",
                    "be",
                ]:
                    return True
                if i == 0:
                    return True
        return False

    def is_patent_procedure(text, tagged):
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

        first_word = text.strip().split()[0].lower()
        if first_word in procedure_starters:
            return True

        procedure_patterns = [
            "according to",
            "following the procedure",
            "as described",
            "using the method",
            "following example",
        ]
        return any(pattern in text.lower() for pattern in procedure_patterns)

    # Tokenize and POS tag
    tokens = word_tokenize(text)
    tagged = pos_tag(tokens)

    if has_passive_voice(tagged) or is_patent_procedure(text, tagged):
        tense_details["past"] = 1
        total_verbs = 1
        return {
            "tense": "past",
            "breakdown": tense_details,
            "breakdown_str": "past: 100%",
            "has_mixed": False,
            "percentages": {"past": 100, "present": 0, "unknown": 0},
            "why_unknown": "",
        }

    # Process each verb
    has_verbs = False
    for i, (word, tag) in enumerate(tagged):
        if tag.startswith("VB"):
            has_verbs = True
            tense = None
            if tag == "VBD" or (
                tag == "VBN" and i > 0 and tagged[i - 1][0].lower() in ["was", "were"]
            ):
                tense = "past"
            elif tag in ["VBP", "VBZ"] or (
                tag == "VBG" and i > 0 and tagged[i - 1][0].lower() in ["is", "are"]
            ):
                tense = "present"

            if tense:
                verb_tenses.append(tense)
                tense_details[tense] += 1

    if not has_verbs:
        why_unknown = "no_verbs_found"
        return {
            "tense": "unknown",
            "breakdown": tense_details,
            "breakdown_str": "",  # Empty for unknown
            "has_mixed": False,
            "percentages": {"past": 0, "present": 0, "unknown": 100},
            "why_unknown": why_unknown,
        }
    elif not verb_tenses:
        why_unknown = "verbs_found_but_not_classified"
        return {
            "tense": "unknown",
            "breakdown": tense_details,
            "breakdown_str": "",  # Empty for unknown
            "has_mixed": False,
            "percentages": {"past": 0, "present": 0, "unknown": 100},
            "why_unknown": why_unknown,
        }

    # Calculate percentages for all tenses and create detailed breakdown
    total_verbs = sum(tense_details.values())
    if total_verbs == 0:
        return {
            "tense": "unknown",
            "breakdown": tense_details,
            "breakdown_str": "",
            "has_mixed": False,
            "percentages": {"past": 0, "present": 0, "unknown": 100},
            "why_unknown": "no_verbs_counted",
        }

    tense_percentages = {
        tense: (count / total_verbs * 100) for tense, count in tense_details.items()
    }

    # Create detailed breakdown string showing all percentages
    breakdown_parts = []
    for tense in ["past", "present"]:  # Order matters for consistency
        if tense_percentages.get(tense, 0) > 0:
            breakdown_parts.append(f"{tense}: {tense_percentages[tense]:.1f}%")

    breakdown_str = ", ".join(breakdown_parts) if breakdown_parts else ""

    # Determine if mixed tense and create detailed description
    significant_tenses = [
        (tense, pct)
        for tense, pct in tense_percentages.items()
        if pct >= 20 and tense != "unknown"
    ]
    has_mixed_tenses = len(significant_tenses) > 1

    # Create detailed mixed tense description
    if has_mixed_tenses:
        significant_tenses.sort(key=lambda x: x[1], reverse=True)  # Sort by percentage
        breakdown_str = "Mixed: " + ", ".join(
            f"{tense} {pct:.1f}%" for tense, pct in significant_tenses
        )

    return {
        "tense": "unknown"
        if not breakdown_parts
        else max(tense_details.items(), key=lambda x: x[1])[0],
        "breakdown": tense_details,
        "breakdown_str": breakdown_str,
        "has_mixed": has_mixed_tenses,
        "percentages": tense_percentages,
        "why_unknown": why_unknown,
        "tense_distribution": significant_tenses if has_mixed_tenses else [],
    }


def process_text_for_tense(input_tuple):
    """Process a text tuple for tense analysis."""
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
    """Process patent examples with detailed tense analysis."""
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

                    for idx, tense_analysis in results:
                        if idx >= len(value):
                            continue

                        example = value[idx]
                        if not isinstance(example, dict):
                            continue

                        example["tense"] = tense_analysis["tense"]
                        example["tense_breakdown"] = tense_analysis["breakdown_str"]
                        example["why_unknown"] = tense_analysis.get("why_unknown", "")

                        # Add percentages to example
                        example["past_percentage"] = tense_analysis["percentages"][
                            "past"
                        ]
                        example["present_percentage"] = tense_analysis["percentages"][
                            "present"
                        ]
                        example["unknown_percentage"] = tense_analysis["percentages"][
                            "unknown"
                        ]

                        tense_counts[tense_analysis["tense"]] += 1
                        if tense_analysis["has_mixed"]:
                            mixed_tense_count += 1

            if total_examples > 0:
                dic[key] = tense_counts
                mixed_tense_percentage = mixed_tense_count / total_examples * 100
                dic[key]["mixed_tense_percentage"] = f"{round(mixed_tense_percentage)}%"

    return dic


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
