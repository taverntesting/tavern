from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/double", methods=["POST"])
def double_number():
    r = request.get_json()

    try:
        number = r["number"]
    except (KeyError, TypeError):
        return jsonify({"error": "no number passed"}), 400

    try:
        double = int(number) * 2
    except ValueError:
        return jsonify({"error": "a number was not passed"}), 400

    return jsonify({"double": double}), 200
