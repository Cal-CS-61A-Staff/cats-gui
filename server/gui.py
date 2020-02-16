"""Web server for the typing GUI."""

import os
import random
import string
from random import randrange

import typing_test
from gui_files.common_server import Server, route, sendto, start
from gui_files import multiplayer_server

PORT = 31415
DEFAULT_SERVER = 'https://cats.cs61a.org'
GUI_FOLDER = "gui_files/"
PARAGRAPH_PATH = "./data/sample_paragraphs.txt"
WORDS_LIST = typing_test.lines_from_file('data/words.txt')
WORDS_SET = set(WORDS_LIST)
LETTER_SETS = [(w, set(w)) for w in WORDS_LIST]
LIMIT = 2
PATHS = {}


@route
def request_paragraph(topics=None):
    """Return a random paragraph."""
    paragraphs = typing_test.lines_from_file(PARAGRAPH_PATH)
    random.shuffle(paragraphs)
    select = typing_test.about(topics) if topics else lambda x: True
    return typing_test.choose(paragraphs, select, 0)


@route
def analyze(prompted_text, typed_text, start_time, end_time):
    """Return [wpm, accuracy]."""
    return {
        "wpm": typing_test.wpm(typed_text, end_time - start_time),
        "accuracy": typing_test.accuracy(typed_text, prompted_text)
    }


def similar(w, v, n):
    """Whether W intersect V contains at least |W|-N and |V|-N elements."""
    intersect = len(w.intersection(v))
    return intersect >= len(w) - n and intersect >= len(v) - n


@route
def autocorrect(word=""):
    """Call autocorrect using the best score function available."""
    raw_word = word
    word = typing_test.lower(typing_test.remove_punctuation(raw_word))
    if word in WORDS_SET or word == '':
        return raw_word

    # Heuristically choose candidate words to score.
    letters = set(word)
    candidates = [w for w, s in LETTER_SETS if similar(s, letters, LIMIT)]

    # Try various diff functions until one doesn't raise an exception.
    for fn in [typing_test.final_diff, typing_test.edit_diff, typing_test.swap_diff]:
        try:
            guess = typing_test.autocorrect(word, candidates, fn, LIMIT)
            return reformat(guess, raw_word)
        except BaseException:
            pass

    return raw_word


def reformat(word, raw_word):
    """Reformat WORD to match the capitalization and punctuation of RAW_WORD."""
    # handle capitalization
    if raw_word != "" and raw_word[0].isupper():
        word = word.capitalize()

    # find the boundaries of the raw word
    first = 0
    while first < len(raw_word) and raw_word[first] in string.punctuation:
        first += 1
    last = len(raw_word) - 1
    while last > first and raw_word[last] in string.punctuation:
        last -= 1

    # add wrapping punctuation to the word
    if raw_word != word:
        word = raw_word[:first] + word
        word = word + raw_word[last + 1:]

    return word


###############
# Multiplayer #
###############

@route
def report_progress(id, typed, prompt):
    """Report progress to the multiplayer server and also return it."""
    typed = typed.split()  # A list of word strings
    prompt = prompt.split()  # A list of word strings

    return typing_test.report_progress(typed, prompt, id, sendto(Server.set_progress))


@route
def fastest_words(prompt, targets):
    """Return a list of word_speed values describing the game."""
    words = ["START"] + prompt.split()
    progress = Server.request_all_progress(targets=targets)
    start_times = [p[0][1] for p in progress]
    word_times = [[typing_test.word_time(w, p[1] - s) for w, p in zip(words, ps)]
                  for s, ps in zip(start_times, progress)]

    return typing_test.fastest_words_report(word_times)


multiplayer_server.create_multiplayer_server()


if __name__ == "__main__" or "gunicorn" in os.environ.get("SERVER_SOFTWARE", ""):
    app = start(PORT, DEFAULT_SERVER, GUI_FOLDER, multiplayer_server.db_init)
