import time
from collections import namedtuple, defaultdict
from datetime import datetime, timedelta
from random import randrange

from gui_files.common_server import route, forward_to_server, server_only
from gui_files.db import connect_db, setup_db

MIN_PLAYERS = 2
MAX_PLAYERS = 4
QUEUE_TIMEOUT = timedelta(seconds=1)
MAX_WAIT = timedelta(seconds=5)


def db_init():
    setup_db("cats")
    with connect_db() as db:
        db(
            """CREATE TABLE IF NOT EXISTS leaderboard (
        username varchar(128),
        wpm double,
        PRIMARY KEY (`username`)
    );"""
        )
        db(
            """CREATE TABLE IF NOT EXISTS memeboard (
        username varchar(128),
        wpm double,
        PRIMARY KEY (`username`)
    );"""
        )


def create_multiplayer_server():
    State = namedtuple("State", ["queue", "game_lookup", "game_data", "progress"])
    State = State({}, {}, {}, defaultdict(list))

    @route
    @forward_to_server
    def request_id():
        return randrange(1000000000)

    @route
    @forward_to_server
    def request_match(id):
        if id in State.game_lookup:
            game_id = State.game_lookup[id]
            return {
                    "start": True,
                    "text": State.game_data[game_id]["text"],
                    "players": State.game_data[game_id]["players"],
                }

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
            import gui
            curr_text = gui.request_paragraph()
            game_id = request_id()

            for player in State.queue:
                State.game_lookup[player] = game_id

            queue = State.queue
            players = list(queue.keys())

            State.game_data[game_id] = {"text": curr_text, "players": players}

            for player in queue:
                State.progress[player] = [(0, time.time())]

            State.queue.clear()

            return {"start": True, "text": curr_text, "players": players}
        else:
            return {"start": False, "numWaiting": len(State.queue)}

    @route
    @server_only
    def set_progress(id, progress):
        """Record progress message."""
        State.progress[id].append((progress, time.time()))
        return ""

    @route
    @forward_to_server
    def request_progress(targets):
        now = {t: State.progress[t][-1] for t in targets}
        elapsed = [[now[t][0], now[t][1] - State.progress[t][0][1]] for t in targets]
        return elapsed

    @route
    @forward_to_server
    def request_all_progress(targets):
        return [State.progress[target] for target in targets]

    @route
    @forward_to_server
    def record_wpm(username, wpm, confirm):
        if len(username) > 30 or wpm > 200 or confirm != "If you want to mess around, send requests to /record_meme! Leave this endpoint for legit submissions please. Don't be a jerk and ruin this for everyone, thanks!":
            return "lol"

        with connect_db() as db:
            db("INSERT INTO leaderboard (username, wpm) VALUES (%s, %s)", [username, wpm])
        return ""

    @route
    @forward_to_server
    def wpm_threshold():
        with connect_db() as db:
            vals = db("SELECT wpm FROM leaderboard ORDER BY wpm DESC LIMIT 20").fetchall()
            return vals[-1][0] if len(vals) >= 20 else 0

    @route
    @forward_to_server
    def leaderboard():
        with connect_db() as db:
            return list(list(x) for x in db("SELECT username, wpm FROM leaderboard ORDER BY wpm DESC LIMIT 20").fetchall())

    @route
    @forward_to_server
    def memeboard():
        with connect_db() as db:
            return list(list(x) for x in db("SELECT username, wpm FROM memeboard ORDER BY wpm DESC LIMIT 20").fetchall())
