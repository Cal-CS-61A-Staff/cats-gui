import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from random import randrange
from urllib.parse import parse_qs

from flask import Flask, jsonify, request, send_from_directory, session
from sqlalchemy import create_engine, text

import gui
import typing_test

app = Flask(__name__, static_url_path="", static_folder="static")
app.config["SECRET_KEY"] = os.urandom(32)

MIN_PLAYERS = 2
MAX_PLAYERS = 4
QUEUE_TIMEOUT = timedelta(seconds=1)
MAX_WAIT = timedelta(seconds=5)


WPM_THRESHOLD = 30


if __name__ == "__main__":
    engine = create_engine("mysql://localhost/cats")
else:
    engine = create_engine(os.getenv("DATABASE_URL"))


with engine.connect() as conn:
    statement = text(
        """CREATE TABLE IF NOT EXISTS leaderboard (
    username varchar(128),
    wpm integer
);"""
    )
    conn.execute(statement)
    statement = text(
        """CREATE TABLE IF NOT EXISTS memeboard (
    username varchar(128),
    wpm integer
);"""
    )
    conn.execute(statement)


@dataclass
class State:
    queue: dict = field(default_factory=dict)
    game_lookup: dict = field(default_factory=dict)
    game_data: dict = field(default_factory=dict)
    progress: dict = field(default_factory=lambda: defaultdict(list))

    delay_tokens: dict = field(default_factory=dict)


State = State()

used_wpm_nonces = {}

def get_from_gui(f, request):
    return f(parse_qs(request.get_data().decode("ascii")))

def passthrough(path):
    def decorator(f):
        @app.route(path, methods=["POST"], endpoint=f.__name__)
        def decorated():
            return jsonify(get_from_gui(f, request))

        return decorated
    return decorator


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/request_paragraph", methods=["POST"])
def request_paragraph():
    paragraph = get_from_gui(gui.request_paragraph, request)
    session.clear()
    session["paragraph"] = paragraph
    return paragraph


@app.route("/analyze", methods=["POST"])
def analyze():
    analysis = get_from_gui(gui.compute_accuracy, request)
    claimed = request.form.get("promptedText")
    typed = request.form.get("typedText")

    if claimed == session.get("paragraph") and 'start' not in session:
        session["start"] = time.time()

    if claimed == session.get("paragraph") and typed == claimed and 'end' not in session:
        session["end"] = time.time()
        wpm_nonce = os.urandom(32)
        while wpm_nonce in used_wpm_nonces:
            wpm_nonce = os.urandom(32)
        session["wpm_nonce"] = wpm_nonce

    return analysis


passthrough("/autocorrect")(gui.autocorrect)
passthrough("/fastest_words")(lambda x: gui.fastest_words(x, lambda targets: [State.progress[target] for target in targets["targets[]"]]))


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

        return jsonify({"start": True, "text": curr_text, "players": list(queue.keys())})
    else:
        return jsonify({"start": False, "numWaiting": len(State.queue)})


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

        with engine.connect() as conn:
            conn.execute("INSERT INTO leaderboard (username, wpm) VALUES (?, ?)", ["<student playing locally>", wpm])
    return "", 204


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
    if "username" not in request.form:
        return jsonify(
            {
                "error": "No username present",
            }
        ), 400
    elif len(request.form["username"]) > 30:
        return jsonify(
            {
                "error": "Username too long",
            }
        ), 400

    if "wpm" not in request.form:
        return jsonify(
            {
                "error": "No WPM present",
            }
        ), 400

    if "start" not in session or "end" not in session or "paragraph" not in session or "wpm_nonce" not in session:
        return jsonify(
            {
                "error": "Unable to calculate real WPM from session",
            }
        ), 400

    if session["wpm_nonce"] in used_wpm_nonces:
        return jsonify(
            {
                "error": "Nonce already used"
            }
        ), 400

    username = request.form.get("username")
    wpm = float(request.form.get("wpm"))

    real_wpm = typing_test.wpm(session["paragraph"], session["end"] - session["start"])

    used_wpm_nonces[session["wpm_nonce"]] = session["wpm_nonce"]
    session.pop("paragraph", None)
    session.pop("start", None)
    session.pop("end", None)
    session.pop("wpm_nonce", None)

    if abs(wpm - real_wpm) > WPM_THRESHOLD:
        return jsonify(
            {
                "error": "Invalid WPM",
            }
        ), 400

    with engine.connect() as conn:
        conn.execute("INSERT INTO leaderboard (username, wpm) VALUES (%s, %s)", [username, wpm])
    return "", 204


@app.route("/record_meme", methods=["POST"])
def record_meme():
    username = request.form.get("username")
    wpm = float(request.form.get("wpm"))

    with engine.connect() as conn:
        conn.execute("INSERT INTO memeboard (username, wpm) VALUES (%s, %s)", [username, wpm])
    return "", 204


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
