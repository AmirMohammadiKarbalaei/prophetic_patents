import nltk
from nltk import pos_tag, word_tokenize


nltk.download("averaged_perceptron_tagger")
nltk.download("punkt")


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
