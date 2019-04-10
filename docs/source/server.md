# Advanced example server code

To run the advanced example yourself you'll need to run a testing server locally using Flask. Just copy the Python code below into a new file and run the following lines to start the server.

```bash
$ export FLASK_APP=server.py
$ flask run
```

```python
# server.py

import sqlite3
import datetime
import functools
from flask import Flask, jsonify, request, g
import jwt


app = Flask(__name__)


SECRET = "CGQgaG7GYvTcpaQZqosLy4"
DATABASE = "/tmp/test_db"


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

        with db:
            try:
                db.execute("CREATE TABLE numbers_table (name TEXT NOT NULL, number INTEGER NOT NULL)")
            except:
                pass

    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route("/login", methods=["POST"])
def login():
    r = request.get_json()

    if r["user"] != "test-user" or r["password"] != "correct-password":
        return jsonify({"error": "Incorrect username/password"}), 401

    payload = {
        "sub": "test-user",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }

    token = jwt.encode(payload, SECRET, algorithm="HS256").decode("utf8")

    return jsonify({"token": token})


def requires_jwt(endpoint):
    """ Makes sure a jwt is in the request before accepting it """

    @functools.wraps(endpoint)
    def check_auth_call(*args, **kwargs):
        token = request.headers.get("Authorization")

        # check token is present
        if not token:
            return jsonify({"error": "No token"}), 401

        token_type, token = token.split(" ")

        if token_type.lower() != "bearer":
            return jsonify({"error": "Wrong token type"}), 401

        try:
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except:
            return jsonify({"error": "Invalid token"}), 401

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

    number = next(row)[0]

    return jsonify({"number": number})
```
