import base64
import gzip
import itertools
import json
import math
import mimetypes
import os
import time
import uuid
from datetime import datetime, timedelta
from hashlib import sha512
from urllib.parse import unquote_plus, urlencode

import jwt
from box import Box
from flask import Flask, Response, jsonify, make_response, redirect, request, session
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
app.config.update(SECRET_KEY="secret")


@app.route("/token", methods=["GET"])
def token():
    return (
        '<div><a src="http://127.0.0.1:5003/verify?token=c9bb34ba-131b-11e8-b642-0ed5f89f718b">Link</a></div>',
        200,
    )


@app.route("/headers", methods=["GET"])
def headers():
    return "OK", 200, {"X-Integration-Value": "_HelloWorld1", "ATestHEader": "orange"}


@app.route("/verify", methods=["GET"])
def verify():
    if request.args.get("token") == "c9bb34ba-131b-11e8-b642-0ed5f89f718b":
        return "", 200
    else:
        return "", 401


@app.route("/get_thing_slow", methods=["GET"])
def get_slow():
    time.sleep(0.25)

    response = {"status": "OK"}
    return jsonify(response), 200


@app.route("/fake_dictionary", methods=["GET"])
def get_fake_dictionary():
    fake = {
        "top": {"Thing": "value", "nested": {"doubly": {"inner": "value"}}},
        "an_integer": 123,
        "a_string": "abc",
        "a_bool": True,
    }

    return jsonify(fake), 200


@app.route("/fake_list", methods=["GET"])
def list_response():
    list_response = ["a", "b", "c", 1, 2, 3, -1.0, -2.0, -3.0]
    return jsonify(list_response), 200


@app.route("/complicated_list", methods=["GET"])
def complicated_list():
    list_response = ["a", {"b": "c"}]
    return jsonify(list_response), 200


@app.route("/nested_list", methods=["GET"])
def nested_list_response():
    response = {"top": ["a", "b", {"key": "val"}]}
    return jsonify(response), 200


@app.route("/fake_upload_file", methods=["POST"])
def upload_fake_file():
    if not request.files:
        return "", 401

    return _handle_files()


def _handle_files():
    for item in request.files.values():
        if item.filename:
            filetype = ".{}".format(item.filename.split(".")[-1])
            if filetype in mimetypes.suffix_map:
                if not item.content_type:
                    return "", 400
    # Try to download each of the files downloaded to /tmp and
    # then remove them
    for key in request.files:
        file_to_save = request.files[key]
        path = os.path.join("/tmp", file_to_save.filename)
        file_to_save.save(path)
    return "", 200


class BadFileUploadException(Exception):
    """Something wrong when uploading files"""


def _verify_is_file_multipart():
    if not mimetypes.inited:
        mimetypes.init()

    if not request.content_type.startswith("multipart/form-data"):
        raise BadFileUploadException("Was not a multipart form upload")

    if not request.files:
        raise BadFileUploadException("No files in request")


@app.route("/fake_upload_file_data", methods=["POST"])
def upload_fake_file_and_data():
    try:
        _verify_is_file_multipart()
    except BadFileUploadException as e:
        return jsonify({"error": str(e)}), 400

    if not request.form.to_dict():
        return "", 400

    return _handle_files()


@app.route("/files_expect_in_order", methods=["POST"])
def upload_specific_files_in_order():
    """Expects a multipart form upload with files in the correct order

    See test_files.tavern.yaml for expected list of files here
    """

    try:
        _verify_is_file_multipart()
    except BadFileUploadException as e:
        return jsonify({"error": str(e)}), 400

    try:
        group_1 = request.files.getlist("group_1")
        if len(group_1) != 2:
            raise Exception(f"expected 2 files in group 1, got {len(group_1)}")
        if group_1[0].filename != "OK.txt":
            raise Exception(
                f"First file in group 1 should be OK.txt, was {group_1[0].filename}"
            )
        if group_1[1].filename != "OK.json.gz":
            raise Exception(
                f"Second file in group 1 should be OK.json.gz, was {group_1[1].filename}"
            )

        group_2 = request.files.getlist("group_2")
        if len(group_2) != 1:
            raise Exception(f"expected 1 files in group 2, got {len(group_2)}")
        if group_2[0].filename != "OK.txt":
            raise Exception(
                f"First file in group 2 should be OK.txt, was {group_2[0].filename}"
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return "", 200


@app.route("/nested/again", methods=["GET"])
def multiple_path_items_response():
    response = {"status": "OK"}
    return jsonify(response), 200


@app.route("/pi", methods=["GET"])
def return_fp_number():
    response = {"pi": math.pi}
    return jsonify(response), 200


@app.route("/expect_dtype", methods=["POST"])
def expect_type():
    body = request.get_json()
    value = body.get("value")
    dtype = body.get("dtype")
    dvalue = body.get("dvalue")

    status = "OK"
    code = 200

    if not value and dtype and dvalue:
        status = "Missing expected type or value"
        code = 400

    if str(type(value)) != f"<class '{dtype}'>":
        status = f"Unexpected type: '{str(type(value))}'"
        code = 400

    if value != dvalue:
        status = f"Unexpected value: '{value}'"
        code = 400

    return jsonify({"status": status}), code


@app.route("/status_code_return", methods=["POST"])
def status_code_return():
    body = request.get_json()
    response = {}
    return jsonify(response), int(body["status_code"])


@app.route("/echo", methods=["POST"])
def echo_values():
    body = request.get_json(silent=True)
    response = body
    return jsonify(response), 200


@app.route("/echo_params", methods=["GET"])
def echo_params():
    params = request.args

    response = {}
    for k, v in params.items():
        unquoted = unquote_plus(v)
        try:
            response[k] = json.loads(unquoted)
        except json.decoder.JSONDecodeError:
            response[k] = unquoted

    return jsonify(response), 200


@app.route("/expect_raw_data", methods=["POST"])
def expect_raw_data():
    raw_data = request.stream.read().decode("utf8").strip()
    if raw_data == "OK":
        response = {"status": "ok"}
        code = 200
    elif raw_data == "DENIED":
        response = {"status": "denied"}
        code = 401
    else:
        response = {"status": f"err: '{raw_data}'"}
        code = 400

    return jsonify(response), code


@app.route("/expect_compressed_data", methods=["POST"])
def expect_compressed_data():
    content_type_header = request.headers.get("content-type")
    if content_type_header != "application/json":
        return jsonify("invalid content type " + content_type_header), 400

    content_encoding_header = request.headers.get("content-encoding")
    if content_encoding_header != "gzip":
        return jsonify("invalid content encoding " + content_encoding_header), 400

    compressed_data = request.stream.read()

    decompressed = gzip.decompress(compressed_data)

    raw_data = decompressed.decode("utf8").strip()

    loaded = json.loads(raw_data)

    if loaded == "OK":
        response = {"status": "ok"}
        code = 200
    else:
        response = {"status": f"err: '{raw_data}'"}
        code = 400

    return jsonify(response), code


@app.route("/form_data", methods=["POST"])
def echo_form_values():
    body = request.get_data()
    key, _, value = body.decode("utf8").partition("=")
    response = {key: value}
    return jsonify(response), 200


@app.route("/stream_file", methods=["GET"])
def stream_file():
    def iter():
        for data in range(1, 10):
            yield bytes(data)

    response = Response(iter(), mimetype="application/octet-stream")
    response.headers["Content-Disposition"] = "attachment; filename=tmp.txt"
    return response


statuses = itertools.cycle(["processing", "ready"])


@app.route("/poll", methods=["GET"])
def poll():
    response = {"status": next(statuses)}
    return jsonify(response)


def _maybe_get_cookie_name():
    return (request.get_json(silent=True) or {}).get("cookie_name", "tavern-cookie")


@app.route("/get_cookie", methods=["POST"])
def give_cookie():
    cookie_name = _maybe_get_cookie_name()
    response = Response()
    response.set_cookie(cookie_name, base64.b64encode(os.urandom(16)).decode("utf8"))
    return response, 200


@app.route("/expect_cookie", methods=["GET"])
def expect_cookie():
    cookie_name = _maybe_get_cookie_name()
    if cookie_name not in request.cookies:
        return (
            jsonify({"error": f"No cookie named {cookie_name} in request"}),
            400,
        )
    else:
        return jsonify({"status": "ok"}), 200


@app.route("/redirect/source", methods=["GET"])
def redirect_to_other_endpoint():
    query_params = urlencode(
        {
            "test_value": "lorem ipsum?",
        }
    )

    return redirect(f"/redirect/destination?{query_params}", 302)


@app.route("/redirect/loop", methods=["GET"])
def redirect_loop():
    try:
        if redirect_loop.tries > 50:
            return redirect("/redirect/destination", 302)
        else:
            redirect_loop.tries += 1
    except AttributeError:
        redirect_loop.tries = 1

    return redirect("/redirect/loop", 302)


@app.route("/redirect/destination", methods=["GET"])
def get_redirected_to_here():
    return jsonify({"status": "successful redirect"}), 200


@app.route("/get_single_json_item", methods=["GET"])
def return_one_item():
    return jsonify("c82bfa63-fd2a-419a-8c06-21cb283fd9f7"), 200


@app.route("/authtest/basic", methods=["GET"])
def expect_basic_auth():
    auth = request.authorization

    if auth is None:
        return jsonify({"status": "No authorisation"}), 403

    if auth.type == "basic":
        if auth.username == "fakeuser" and auth.password == "fakepass":
            return (
                jsonify(
                    {
                        "auth_type": auth.type,
                        "auth_user": auth.username,
                        "auth_pass": auth.password,
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "Wrong username/password"}), 401
    else:
        return jsonify({"error": "unrecognised auth type"}), 403


@app.route("/jmes/return_empty_paged", methods=["GET"])
def return_empty_paged():
    return jsonify({"pages": 0, "data": []}), 200


@app.route("/jmes/with_dot", methods=["GET"])
def return_with_dot():
    return jsonify({"data.a": "a", "data.b": "b"}), 200


@app.route("/uuid/v4", methods=["GET"])
def get_uuid_v4():
    return jsonify({"uuid": uuid.uuid4()}), 200


@app.route("/707-regression", methods=["GET"])
def get_707():
    return jsonify({"a": 1, "b": {"first": 10, "second": 20}, "c": 2})


users = {"mark": {"password": "password", "regular": "foo", "protected": "bar"}}

serializer = URLSafeTimedSerializer(
    secret_key="secret",
    salt="cookie",
    signer_kwargs={"key_derivation": "hmac", "digest_method": sha512},
)


@app.route("/withsession/login", methods=["POST"])
def login():
    r = request.get_json()
    username = r["username"]
    password = r["password"]

    if password == users[username]["password"]:
        session["user"] = username
        response = make_response("", 200)
        response.set_cookie(
            "remember",
            value=serializer.dumps(username),
            expires=datetime.utcnow() + timedelta(days=30),
            httponly=True,
        )
        return response

    return "", 401


@app.route("/withsession/regular", methods=["GET"])
def regular():
    username = session.get("user")

    if not username:
        remember = request.cookies.get("remember")
        if remember:
            username = serializer.loads(remember, max_age=3600)

    if username:
        return jsonify(regular=users[username]["regular"]), 200

    return "", 401


@app.route("/withsession/protected", methods=["GET"])
def protected():
    username = session.get("user")
    if username:
        return jsonify(protected=users[username]["protected"]), 200
    return "", 401


@app.route("/606-regression-list", methods=["GET"])
def get_606_list():
    return jsonify([])


@app.route("/606-regression-dict", methods=["GET"])
def get_606_dict():
    return jsonify({})


@app.route("/sub-path-query", methods=["POST"])
def sub_path_query():
    r = request.get_json(force=True)
    sub_path = r["sub_path"]

    return jsonify({"result": Box(r, box_dots=True)[sub_path]})


@app.route("/magic-multi-method", methods=["GET", "POST", "DELETE"])
def get_any_method():
    return jsonify({"method": request.method})


@app.route("/get_jwt", methods=["POST"])
def get_jwt():
    secret = "240c8c9c-39b9-426b-9503-3126f96c2eaf"
    audience = "testserver"

    r = request.get_json()

    if r["user"] != "test-user" or r["password"] != "correct-password":
        return jsonify({"error": "Incorrect username/password"}), 401

    payload = {
        "sub": "test-user",
        "aud": audience,
        "exp": datetime.utcnow() + timedelta(hours=1),
    }

    token = jwt.encode(payload, secret, algorithm="HS256")

    return jsonify({"jwt": token})
