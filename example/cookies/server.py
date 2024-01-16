import contextlib
import functools
import sqlite3

from flask import Flask, g, jsonify, request, session

app = Flask(__name__)
app.secret_key = "t1uNraxw+9oxUyCuXHO2G0u38ig="


DATABASE = "/tmp/test_db"
SERVERNAME = "testserver"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

        with db:
            with contextlib.suppress(Exception):
                db.execute(
                    "CREATE TABLE numbers_table (name TEXT NOT NULL, number INTEGER NOT NULL)"
                )

    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.route("/login", methods=["POST"])
def login():
    r = request.get_json()

    if r["user"] != "test-user" or r["password"] != "correct-password":
        return jsonify({"error": "Incorrect username/password"}), 401

    session["user"] = "test-user"

    return jsonify({"status": "logged in"}), 200


def requires_jwt(endpoint):
    """Makes sure a jwt is in the request before accepting it"""

    @functools.wraps(endpoint)
    def check_auth_call(*args, **kwargs):
        if not session:
            return jsonify({"error": "No session cookie"}), 401

        return endpoint(*args, **kwargs)

    return check_auth_call


@app.route("/numbers", methods=["POST"])
@requires_jwt
def add_number():
    r = request.get_json()

    try:
        r["number"]
        r["name"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key"}), 400

    db = get_db()

    with db:
        db.execute("INSERT INTO numbers_table VALUES (:name, :number)", r)

    return jsonify({}), 201


@app.route("/numbers", methods=["GET"])
@requires_jwt
def get_number():
    r = request.args

    try:
        r["name"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key"}), 400

    db = get_db()

    with db:
        row = db.execute("SELECT number FROM numbers_table WHERE name IS :name", r)

    try:
        number = next(row)[0]
    except StopIteration:
        return jsonify({"error": "Unknown number"}), 404

    return jsonify({"number": number})


@app.route("/double", methods=["POST"])
@requires_jwt
def double_number():
    r = request.get_json()

    try:
        r["name"]
    except (KeyError, TypeError):
        return jsonify({"error": "no number passed"}), 400

    db = get_db()

    with db:
        db.execute("UPDATE numbers_table SET number = number*2 WHERE name IS :name", r)
        row = db.execute("SELECT number FROM numbers_table WHERE name IS :name", r)

    try:
        double = next(row)[0]
    except StopIteration:
        return jsonify({"error": "Unknown number"}), 404

    return jsonify({"number": double})


@app.route("/reset", methods=["POST"])
def reset_db():
    db = get_db()

    with db:
        db.execute("DELETE FROM numbers_table")

    return "", 204
