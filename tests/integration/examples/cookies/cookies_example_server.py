import functools
import sqlite3

from flask import Blueprint, jsonify, request, g, session


blueprint = Blueprint("example_cookies", __name__)

DATABASE = "/tmp/test_db"
SERVERNAME = "testserver"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

        with db:
            try:
                db.execute(
                    "CREATE TABLE numbers_table (name TEXT NOT NULL, number INTEGER NOT NULL)"
                )
            except:
                pass

    return db


@blueprint.route("/login", methods=["POST"])
def login():
    r = request.get_json()

    if r["user"] != "test-user" or r["password"] != "correct-password":
        return jsonify({"error": "Incorrect username/password"}), 401

    session["user"] = "test-user"

    return jsonify({"status": "logged in"}), 200


def requires_session_cookie(endpoint):
    """ Makes sure a session is associated with the request before accepting it """

    @functools.wraps(endpoint)
    def check_auth_call(*args, **kwargs):
        if not session:
            return jsonify({"error": "No session cookie"}), 401

        return endpoint(*args, **kwargs)

    return check_auth_call


@blueprint.route("/numbers", methods=["POST"])
@requires_session_cookie
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


@blueprint.route("/numbers", methods=["GET"])
@requires_session_cookie
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


@blueprint.route("/double", methods=["POST"])
@requires_session_cookie
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


@blueprint.route("/reset", methods=["POST"])
def reset_db():
    db = get_db()

    with db:
        db.execute("DELETE FROM numbers_table")

    return "", 204
