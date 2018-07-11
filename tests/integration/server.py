import math
import os
from flask import Flask, request, jsonify, Response


app = Flask(__name__)


@app.route("/token", methods=["GET"])
def token():
    return '<div><a src="http://127.0.0.1:5003/verify?token=c9bb34ba-131b-11e8-b642-0ed5f89f718b">Link</a></div>', 200


@app.route("/headers", methods=["GET"])
def headers():
    return 'OK', 200, {
        'X-Integration-Value': "_HelloWorld1",
        "ATestHEader": "orange",
    }


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
    dvalue = body.get("dvalue")

    status = "OK"
    code = 200

    if not value and dtype and dvalue:
        status = "Missing expected type or value"
        code = 400

    if str(type(value)) != "<class '{}'>".format(dtype):
        status = "Unexpected type: '{}'".format(str(type(value)))
        code = 400

    if value != dvalue:
        status = "Unexpected value: '{}'".format(value)
        code = 400

    return jsonify({"status": status}), code


@app.route("/status_code_return", methods=["POST"])
def status_code_return():
    body = request.get_json()
    response = {}
    return jsonify(response), int(body["status_code"])


@app.route("/echo", methods=["POST"])
def echo_values():
    body = request.get_json()
    response = body
    return jsonify(response), 200


@app.route("/expect_raw_data", methods=["POST"])
def expect_raw_data():
    raw_data = request.stream.read().decode("utf8")
    if raw_data == "OK":
        response = {
            "status": "ok",
        }
        code = 200
    elif raw_data == "DENIED":
        response = {
            "status": "denied",
        }
        code = 401
    else:
        response = {
            "status": "err: '{}'".format(raw_data),
        }
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
        for data in range(1,10):
            yield bytes(data)
    response = Response(iter(), mimetype='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename=tmp.txt'
    return response
