from flask import Flask, request, jsonify


app = Flask(__name__)


@app.route("/token", methods=["GET"])
def token():
    return '<div><a src="http://127.0.0.1:5000/verify?token=c9bb34ba-131b-11e8-b642-0ed5f89f718b">Link</a></div>', 200

@app.route("/verify", methods=["GET"])
def verify():
    if request.args.get('token') == 'c9bb34ba-131b-11e8-b642-0ed5f89f718b':
        return '', 200
    else:
        return '', 401


@app.route("/fake_list", methods=["GET"])
def list_response():
    list_response = [
        "a",
        "b",
        "c",
    ]
    return jsonify(list_response), 200
