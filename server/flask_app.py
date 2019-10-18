import base64
import io
import os
import random
import time

from claptcha import Claptcha
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from random import randrange
from urllib.parse import parse_qs

from flask import Flask, jsonify, make_response, request, send_from_directory
from sqlalchemy import create_engine, text
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

import gui
import typing_test

from gui import WORDS_LIST

app = Flask(__name__, static_url_path="", static_folder="static")

MIN_PLAYERS = 2
MAX_PLAYERS = 4
QUEUE_TIMEOUT = timedelta(seconds=1)
MAX_WAIT = timedelta(seconds=5)

CAPTCHA_WPM_THRESHOLD = 100
CAPTCHA_WORD_LENGTH_RANGE = (4, 6)
CAPTCHA_LAST_POSSIBLE_INDEX = 999
CAPTCHA_NUM_WORDS = 40
CAPTCHA_ACCURACY_THRESHOLD = 80.0
CAPTCHA_VERIFIED_WPM_SCALE = 1.5
VERIFY_PERIOD = 86400

P_TOKEN_VALIDITY = 3600
S_TOKEN_VALIDITY = 3600
WPM_TOKEN_VALIDITY = 3600
CAPTCHA_TOKEN_VALIDITY = 3600
TIMESTAMP_THRESHOLD = 60


if __name__ == "__main__":
    engine = create_engine("mysql://localhost/cats")
else:
    engine = create_engine(os.getenv("DATABASE_URL"))


with engine.connect() as conn:
    statement = text(
        """CREATE TABLE IF NOT EXISTS leaderboard (
    username varchar(32),
    wpm integer
);"""
    )
    conn.execute(statement)
    statement = text(
        """CREATE TABLE IF NOT EXISTS memeboard (
    username varchar(1024),
    wpm integer
);"""
    )
    conn.execute(statement)


p_fernet = Fernet(Fernet.generate_key())
s_fernet = Fernet(Fernet.generate_key())
wpm_fernet = Fernet(Fernet.generate_key())
captcha_fernet = Fernet(Fernet.generate_key())
verify_fernet = Fernet(Fernet.generate_key())

p_tokens_used = {}
s_tokens_used = {}
wpm_tokens_used = {}
captcha_tokens_used = {}


@dataclass
class State:
    queue: dict = field(default_factory=dict)
    game_lookup: dict = field(default_factory=dict)
    game_data: dict = field(default_factory=dict)
    progress: dict = field(default_factory=lambda: defaultdict(list))

    delay_tokens: dict = field(default_factory=dict)


State = State()


def passthrough(path):
    def decorator(f):
        @app.route(path, methods=["POST"], endpoint=f.__name__)
        def decorated():
            return jsonify(f(parse_qs(request.get_data().decode("ascii"))))

        return decorated
    return decorator


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


passthrough("/autocorrect")(gui.autocorrect)
passthrough("/fastest_words")(lambda x: gui.fastest_words(x, lambda targets: [State.progress[target] for target in targets["targets[]"]]))


def hash_message(message):
    sha256 = hashes.Hash(hashes.SHA256(), backend=default_backend())
    sha256.update(message)
    return sha256.finalize()


def generate_p_token(paragraph):
    return p_fernet.encrypt(hash_message(paragraph.encode("utf-8"))).decode("utf-8")


@app.route("/request_paragraph", methods=["POST"])
def request_paragraph():
    response = gui.request_paragraph(parse_qs(request.get_data().decode("ascii")))
    response["pToken"] = generate_p_token(response["paragraph"])
    return jsonify(response)


def verify_token(token, fernet, used_tokens, validity):
    try:
        timestamp = fernet.extract_timestamp(token)
    except:
        return False
    if token in used_tokens:
        return False
    if time.time() - timestamp > validity:
        return False
    return True


def mark_token_used(token, fernet, used_tokens, validity):
    for used_token, used_timestamp in list(used_tokens.items()):
        if used_timestamp - time.time() > validity:
            used_tokens.pop(used_token)

    timestamp = fernet.extract_timestamp(token)
    used_tokens[token] = timestamp


def verify_paragraph_token(token, paragraph):
    if not verify_token(token, p_fernet, p_tokens_used, P_TOKEN_VALIDITY):
        return False
    contents = p_fernet.decrypt(token)
    if contents != hash_message(paragraph.encode("utf-8")):
        return False
    mark_token_used(token, p_fernet, p_tokens_used, P_TOKEN_VALIDITY)
    return True


def verify_start_token(token, paragraph, start_time, end_time):
    if not verify_token(token, s_fernet, s_tokens_used, S_TOKEN_VALIDITY):
        return False
    contents = s_fernet.decrypt(token)
    timestamp = s_fernet.extract_timestamp(token)
    if contents != hash_message(paragraph.encode("utf-8")):
        return False
    if abs(timestamp - start_time) > TIMESTAMP_THRESHOLD:
        return False
    if abs(time.time() - end_time) > TIMESTAMP_THRESHOLD:
        return False
    mark_token_used(token, s_fernet, s_tokens_used, S_TOKEN_VALIDITY)
    return True


def retreive_verified_wpm(token):
    if verify_token(token, verify_fernet, {}, VERIFY_PERIOD):
        return float(verify_fernet.decrypt(token).decode("utf-8"))
    else:
        return 0.0


@app.route("/analyze", methods=["POST"])
def analyze():
    analysis = gui.compute_accuracy(parse_qs(request.get_data().decode("ascii")))
    paragraph = request.form.get("promptedText")
    typed = request.form.get("typedText")

    if request.form.get("pToken"):
        p_token = request.form.get("pToken").encode("utf-8")
        if verify_paragraph_token(p_token, paragraph):
            analysis["sToken"] = s_fernet.encrypt(hash_message(paragraph.encode("utf-8"))).decode("utf-8")
    elif request.form.get("sToken") and paragraph == typed:
        s_token = request.form.get("sToken").encode("utf-8")
        wpm = analysis["wpm"]
        verified_wpm = 0.0 if not request.cookies.get("verified_wpm") else retreive_verified_wpm(request.cookies.get("verified_wpm").encode("utf-8"))
        if verify_start_token(s_token, paragraph, float(request.form.get("startTime")), float(request.form.get("endTime"))) and wpm <= 200:
            analysis["wpmToken"] = wpm_fernet.encrypt(str(wpm).encode("utf-8")).decode("utf-8")
            analysis["captchaRequired"] = wpm >= CAPTCHA_WPM_THRESHOLD and wpm > verified_wpm

    return jsonify(analysis)


def get_id():
    return randrange(1000000000)


@app.route("/request_id", methods=["POST"])
def request_id():
    return jsonify(get_id())


@app.route("/request_match", methods=["POST"])
def request_match():
    id = request.form.get("id")

    if id in State.game_lookup:
        game_id = State.game_lookup[id]
        return jsonify(
            {
                "start": True,
                "text": State.game_data[game_id]["text"],
                "pToken": generate_p_token(State.game_data[game_id]["text"]),
                "players": State.game_data[game_id]["players"],
            }
        )

    if id not in State.queue:
        State.queue[id] = [None, datetime.now()]

    State.queue[id][0] = datetime.now()

    to_remove = []

    for player, (recent_time, join_time) in State.queue.items():
        if datetime.now() - recent_time > QUEUE_TIMEOUT:
            to_remove.append(player)

    for player in to_remove:
        del State.queue[player]

    if len(State.queue) >= MAX_PLAYERS or \
            max(datetime.now() - join_time for recent_time, join_time in State.queue.values()) >= MAX_WAIT and \
            len(State.queue) >= MIN_PLAYERS:
        # start game!
        curr_text = gui.request_paragraph(None)
        game_id = get_id()

        for player in State.queue:
            State.game_lookup[player] = game_id

        queue = State.queue

        State.game_data[game_id] = {"text": curr_text, "players": list(queue.keys())}

        for player in queue:
            State.progress[player] = [(0, time.time())]

        State.queue = {}

        return jsonify(
            {
                "start": True,
                "text": curr_text,
                "pToken": generate_p_token(curr_text),
                "players": list(queue.keys()),
            }
        )
    else:
        return jsonify(
            {
                "start": False,
                "numWaiting": len(State.queue),
            }
        )


@app.route("/report_progress", methods=["POST"])
def report_progress():
    """Report progress as a string of typed words."""
    id = request.form.get("id")
    typed = request.form.get("typed").split()   # A list of word strings
    prompt = request.form.get("prompt").split() # A list of word strings

    def set_progress(data):
        id, progress = data["id"], float(data["progress"])
        record_progress(id, progress, True)

    return jsonify(typing_test.report_progress(typed, prompt, id, set_progress))


@app.route("/set_progress", methods=["POST"])
def set_progress():
    """Report progress as a fraction of correctly typed words."""
    id = request.form.get("id")
    progress = float(request.form.get("progress"))
    updated = request.form.get("progress", False)
    return record_progress(id, progress, updated)


def record_progress(id, progress, updated):
    """Record progress message."""
    updated = request.form.get("updated", False)
    State.progress[id].append((progress, time.time()))
    if progress == 1 and not updated:
        game_id = State.game_lookup[id]
        prompt = State.game_data[game_id]["text"]
        wpm = len(prompt) / (time.time() - State.progress[id][0][1]) * 60 / 5

        if wpm > 200:
            return ""

        with engine.connect() as conn:
            conn.execute("INSERT INTO leaderboard (username, wpm) VALUES (?, ?)", ["<student playing locally>", wpm])
    return ""


@app.route("/request_progress", methods=["POST"])
def request_progress():
    targets = request.form.getlist("targets[]")
    now = {t: State.progress[t][-1] for t in targets}
    elapsed = [[now[t][0], now[t][1] - State.progress[t][0][1]] for t in targets]
    return jsonify(elapsed)


@app.route("/request_all_progress", methods=["POST"])
def request_all_progress():
    targets = request.form.getlist("targets[]")
    out = [State.progress[target] for target in targets]
    return jsonify(out)


def verify_wpm_token(token, wpm):
    if not verify_token(token, wpm_fernet, wpm_tokens_used, WPM_TOKEN_VALIDITY):
        return False
    contents = float(wpm_fernet.decrypt(token).decode('utf-8'))
    if round(contents, 1) != round(wpm, 1):
        return False
    mark_token_used(token, wpm_fernet, wpm_tokens_used, WPM_TOKEN_VALIDITY)
    return True


@app.route("/record_wpm", methods=["POST"])
def record_name():
    username = request.form.get("username")
    wpm = float(request.form.get("wpm"))
    wpm_token = request.form.get("wpmToken").encode("utf-8")
    verified_wpm = 0.0 if not request.cookies.get("verified_wpm") else retreive_verified_wpm(request.cookies.get("verified_wpm").encode("utf-8"))
    if not verify_wpm_token(wpm_token, wpm):
        return jsonify(
            {
                "response": "Invalid WPM or WPM token",
            }
        ), 400
    if len(username) > 32:
        return jsonify(
            {
                "response": "Username too long",
            }
        ), 400
    if wpm >= CAPTCHA_WPM_THRESHOLD and wpm > verified_wpm:
        return jsonify(
            {
                "response": "CAPTCHA verification failed",
            }
        ), 400
    with engine.connect() as conn:
        conn.execute("INSERT INTO leaderboard (username, wpm) VALUES (%s, %s)", [username, wpm])
    return ""


@app.route("/record_meme", methods=["POST"])
def record_meme():
    username = request.form.get("username")
    wpm = float(request.form.get("wpm"))
    if len(username) > 1024:
        return jsonify(
            {
                "response": "Make it shorter!",
            }
        ), 400
    with engine.connect() as conn:
        conn.execute("INSERT INTO memeboard (username, wpm) VALUES (%s, %s)", [username, wpm])
    return ""


@app.route("/wpm_threshold", methods=["POST"])
def wpm_threshold():
    with engine.connect() as conn:
        vals = conn.execute("SELECT wpm FROM leaderboard ORDER BY wpm DESC LIMIT 20").fetchall()
        return jsonify(vals[-1] if len(vals) >= 20 else 0)


@app.route("/leaderboard", methods=["POST"])
def leaderboard():
    with engine.connect() as conn:
        return jsonify(list(list(x) for x in conn.execute("SELECT username, wpm FROM leaderboard ORDER BY wpm DESC LIMIT 20").fetchall()))


@app.route("/memeboard", methods=["POST"])
def memeboard():
    with engine.connect() as conn:
        return jsonify(list(list(x) for x in conn.execute("SELECT username, wpm FROM memeboard ORDER BY wpm DESC LIMIT 20").fetchall()))


def build_captcha_text():
    possible_words = WORDS_LIST[:CAPTCHA_LAST_POSSIBLE_INDEX]
    possible_words = [word for word in possible_words if CAPTCHA_WORD_LENGTH_RANGE[0] <= len(word) <= CAPTCHA_WORD_LENGTH_RANGE[1]]
    return " ".join(random.sample(possible_words, CAPTCHA_NUM_WORDS))


@app.route("/get_captcha", methods=["GET"])
def get_captcha():
    captcha_text = build_captcha_text()
    response = { "captchaUris": [] }
    for word in captcha_text.split(" "):
        with io.BytesIO() as out:
            claptcha = Claptcha(word, "FreeMono.ttf", margin=(20, 10))
            image_b64 = base64.b64encode(claptcha.bytes[1].getvalue()).decode("utf-8")
            response["captchaUris"].append("data:image/png;base64," + image_b64)
    response["captchaToken"] = captcha_fernet.encrypt(captcha_text.encode("utf-8")).decode("utf-8")
    return jsonify(response)


def analyze_captcha(captcha_token, typed_captcha):
    if not verify_token(captcha_token, captcha_fernet, captcha_tokens_used, CAPTCHA_TOKEN_VALIDITY):
        return 0.0
    mark_token_used(captcha_token, captcha_fernet, captcha_tokens_used, CAPTCHA_TOKEN_VALIDITY)
    captcha = captcha_fernet.decrypt(captcha_token).decode("utf-8")
    captcha_wpm = typing_test.wpm(typed_captcha, time.time() - captcha_fernet.extract_timestamp(captcha_token))
    captcha_accuracy = typing_test.accuracy(typed_captcha, captcha) * len(typed_captcha.split(" ")) / CAPTCHA_NUM_WORDS
    return captcha_wpm, captcha_accuracy


@app.route("/submit_captcha", methods=["POST"])
def submit_captcha():
    captcha_token = request.form.get("captchaToken").encode("utf-8")
    typed_captcha = request.form.get("typedCaptcha")
    captcha_wpm, captcha_accuracy = analyze_captcha(captcha_token, typed_captcha)
    if captcha_accuracy >= CAPTCHA_ACCURACY_THRESHOLD:
        verified_wpm = captcha_wpm * CAPTCHA_VERIFIED_WPM_SCALE
        verify_token = verify_fernet.encrypt(str(verified_wpm).encode("utf-8"))
        response = make_response(jsonify(
            {
                "passed": True,
                "wpm": captcha_wpm,
                "accuracy": captcha_accuracy,
                "verified": verified_wpm,
            }
        ))
        response.set_cookie("verified_wpm", verify_token.decode("utf-8"), max_age=VERIFY_PERIOD)
        return response
    else:
        return jsonify(
            {
                "passed": False,
                "wpm": captcha_wpm,
                "accuracy": captcha_accuracy,
            }
        )


if __name__ == "__main__":
    app.run(port=gui.PORT, threaded=False)
