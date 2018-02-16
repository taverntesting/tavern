from flask import Flask, jsonify, request


app = Flask(__name__)


@app.route("/text", methods=["GET"])
def text():
    return "text@example.com", 200
