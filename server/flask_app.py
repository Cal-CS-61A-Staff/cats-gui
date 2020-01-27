import base64
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from random import randrange
from urllib.parse import parse_qs

import jwt
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import create_engine, text

import gui
import typing_test

app = Flask(__name__, static_url_path="", static_folder="static")

MIN_PLAYERS = 2
MAX_PLAYERS = 4
QUEUE_TIMEOUT = timedelta(seconds=1)
MAX_WAIT = timedelta(seconds=5)

P_TOKEN_VALIDITY = 3600
S_TOKEN_VALIDITY = 3600
WPM_TOKEN_VALIDITY = 3600
TIMESTAMP_THRESHOLD = 60


token_key = "secret key"


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


p_tokens_used = {}
s_tokens_used = {}
wpm_tokens_used = {}


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
    return sha256(message).digest()


def generate_p_token(paragraph):
    print(paragraph)
    p_hash = base64.encodebytes(hash_message(paragraph.encode("utf-8"))).decode("utf-8")
    return jwt.encode({
        "hash": p_hash,
        "exp": round(time.time()) + P_TOKEN_VALIDITY,
    }, token_key).decode("utf-8")


def generate_s_token(paragraph):
    s_hash = base64.encodestring(hash_message(paragraph.encode("utf-8"))).decode("utf-8")
    return jwt.encode({
        "hash": s_hash,
        "iat": round(time.time()),
        "exp": round(time.time()) + S_TOKEN_VALIDITY,
    }, token_key).decode("utf-8")


def generate_wpm_token(wpm):
    return jwt.encode({
        "wpm": wpm,
        "exp": round(time.time()) + WPM_TOKEN_VALIDITY,
    }, token_key).decode("utf-8")


def verify_token(token, used_tokens):
    if token in used_tokens:
        return False
    try:
        jwt.decode(token, token_key)
        return True
    except jwt.exceptions.ExpiredSignatureError:
        return False


def mark_token_used(token, used_tokens):
    for used_token, exp in list(used_tokens.items()):
        if exp < time.time():
            used_tokens.pop(used_token)

    exp = jwt.decode(token, verify=False)["exp"]
    used_tokens[token] = exp


def verify_paragraph_token(token, paragraph):
    if not verify_token(token, p_tokens_used):
        return False
    claims = jwt.decode(token, verify=False)
    p_hash = base64.decodebytes(claims["hash"].encode("utf-8"))
    if p_hash != hash_message(paragraph.encode("utf-8")):
        return False
    mark_token_used(token, p_tokens_used)
    return True


def verify_start_token(token, paragraph, start_time, end_time):
    if not verify_token(token, s_tokens_used):
        return False
    claims = jwt.decode(token, verify=False)
    s_hash = base64.decodebytes(claims["hash"].encode("utf-8"))
    timestamp = claims["iat"]
    if s_hash != hash_message(paragraph.encode("utf-8")):
        return False
    if abs(timestamp - start_time) > TIMESTAMP_THRESHOLD:
        return False
    mark_token_used(token, s_tokens_used)
    return True


def verify_wpm_token(token, wpm):
    if not verify_token(token, wpm_tokens_used):
        return False
    claims = jwt.decode(token, verify=False)
    claimed_wpm = claims["wpm"]
    if round(claimed_wpm, 1) != round(wpm, 1):
        return False
    mark_token_used(token, wpm_tokens_used)
    return True


@app.route("/request_paragraph", methods=["POST"])
def request_paragraph():
    response = gui.request_paragraph(parse_qs(request.get_data().decode("ascii")))
    response["pToken"] = generate_p_token(response["paragraph"])
    return jsonify(response)


@app.route("/analyze", methods=["POST"])
def analyze():
    analysis = gui.compute_accuracy(parse_qs(request.get_data().decode("ascii")))
    paragraph = request.form.get("promptedText")
    typed = request.form.get("typedText")

    if request.form.get("pToken"):
        p_token = request.form.get("pToken").encode("utf-8")
        if verify_paragraph_token(p_token, paragraph):
            analysis["sToken"] = generate_s_token(paragraph)
    elif request.form.get("sToken") and paragraph == typed:
        s_token = request.form.get("sToken").encode("utf-8")
        wpm = analysis["wpm"]
        if verify_start_token(s_token, paragraph, float(request.form.get("startTime")), float(request.form.get("endTime"))) and wpm <= 200:
            analysis["wpmToken"] = generate_wpm_token(wpm)

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
        curr_text = gui.request_paragraph(None)["paragraph"]
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


@app.route("/record_wpm", methods=["POST"])
def record_name():
    username = request.form.get("username")
    wpm = float(request.form.get("wpm"))
    wpm_token = request.form.get("wpmToken").encode("utf-8")
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


if __name__ == "__main__":
    app.run(port=gui.PORT, threaded=False)
