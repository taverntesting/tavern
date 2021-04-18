import datetime
import functools

from flask import Flask, jsonify, request
import jwt

app = Flask(__name__)

SECRET = "CGQgaG7GYvTcpaQZqosLy5"
DATABASE = "/tmp/test_db"
SERVERNAME = "testserver"


@app.route("/login", methods=["POST"])
def login():
    r = request.get_json()

    if r["user"] != "test-user" or r["password"] != "correct-password":
        return jsonify({"error": "Incorrect username/password"}), 401

    payload = {
        "sub": "test-user",
        "aud": SERVERNAME,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
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
            jwt.decode(token, SECRET, audience=SERVERNAME, algorithms=["HS256"])
        except:
            return jsonify({"error": "Invalid token"}), 401

        return endpoint(*args, **kwargs)

    return check_auth_call


@app.route("/ping", methods=["GET"])
@requires_jwt
def ping():
    return jsonify({"data": "pong"}), 200


@app.route("/hello/<name>", methods=["GET"])
@requires_jwt
def hello(name):
    return jsonify({"data": "Hello, {}".format(name)}), 200
