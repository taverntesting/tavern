import math
import os
from flask import Flask, request, jsonify


app = Flask(__name__)


@app.route("/token", methods=["GET"])
def token():
    return '<div><a src="http://127.0.0.1:5003/verify?token=c9bb34ba-131b-11e8-b642-0ed5f89f718b">Link</a></div>', 200


@app.route("/headers", methods=["GET"])
def headers():
    return 'OK', 200, {'X-Integration-Value': "_HelloWorld1"}


@app.route("/verify", methods=["GET"])
def verify():
    if request.args.get('token') == 'c9bb34ba-131b-11e8-b642-0ed5f89f718b':
        return '', 200
    else:
        return '', 401


@app.route("/fake_dictionary", methods=["GET"])
def get_fake_dictionary():
    fake = {
        "top": {
            "Thing": "value",
            "nested": {
                "doubly": {
                    "inner": "value",
                }
            }
        },
        "an_integer": 123,
        "a_string": "abc",
        "a_bool": True,
    }

    return jsonify(fake), 200


@app.route("/fake_list", methods=["GET"])
def list_response():
    list_response = [
        "a",
        "b",
        "c",
        1,
        2,
        3,
        -1.0,
        -2.0,
        -3.0,
    ]
    return jsonify(list_response), 200


@app.route("/nested_list", methods=["GET"])
def nested_list_response():
    response = {
        "top": [
            "a",
            "b",
            {
                "key": "val",
            }
        ]
    }
    return jsonify(response), 200


@app.route("/fake_upload_file", methods=["POST"])
def upload_fake_file():
    if not request.files:
        return '', 401

    # Try to download each of the files downloaded to /tmp and
    # then remove them
    for key in request.files:
        file_to_save = request.files[key]
        path = os.path.join("/tmp", file_to_save.filename)
        file_to_save.save(path)

    return '', 200


@app.route("/nested/again", methods=["GET"])
def multiple_path_items_response():
    response = {
        "status": "OK",
    }
    return jsonify(response), 200


@app.route("/pi", methods=["GET"])
def return_fp_number():
    response = {
        "pi": math.pi
    }
    return jsonify(response), 200


@app.route("/expect_dtype", methods=["POST"])
def expect_type():
    body = request.get_json()
    value = body.get("value")
    dtype = body.get("dtype")

    if not value and dtype:
        return "", 400

    if str(type(value)) != "<class '{}'>".format(dtype):
        return "", 400

    return "", 200


@app.route("/echo", methods=["POST"])
def echo_values():
    body = request.get_json()
    response = body
    return jsonify(response), 200


@app.route("/form_data", methods=["POST"])
def echo_form_values():
    body = request.get_data()
    key, _, value = body.decode("utf8").partition("=")
    response = {key: value}
    return jsonify(response), 200
