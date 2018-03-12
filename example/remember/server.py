from flask import Flask, jsonify, request, make_response, session
from itsdangerous import URLSafeTimedSerializer
from datetime import timedelta, datetime
from hashlib import sha512

app = Flask(__name__)
app.config.update(
    SECRET_KEY = 'secret'
)

users = {
    'mark': {
        'password': 'password',
        'regular': 'foo',
        'protected': 'bar'
    }
}

serializer = URLSafeTimedSerializer(
    secret_key = 'secret',
    salt = 'cookie',
    signer_kwargs = dict(
        key_derivation = 'hmac',
        digest_method = sha512
    )
)


@app.route("/login", methods=["POST"])
def login():
    r = request.get_json()
    username = r["username"]
    password = r["password"]

    if password == users[username]['password']:
        session['user'] = username
        response = make_response('', 200)
        response.set_cookie(
            'remember',
            value = serializer.dumps(username),
            expires = datetime.utcnow() + timedelta(days = 30),
            httponly = True,
        )
        return response

    return '', 401


@app.route("/regular", methods=["GET"])
def regular():
    username = session.get('user')

    if not username:
        remember = request.cookies.get('remember')
        if remember:
            username = serializer.loads(remember, max_age = 3600)

    if username:
        return jsonify(regular = users[username]['regular']), 200

    return '', 401


@app.route("/protected", methods=["GET"])
def protected():
    username = session.get('user')
    if username:
        return jsonify(protected = users[username]['protected']), 200
    return '', 401
