import sqlite3
import logging
import logging.config
import yaml
from flask import Flask, jsonify, request, g


import paho.mqtt.client as paho


app = Flask(__name__)
application = app


DATABASE = "/tmp/test_db"


def on_message_callback(client, userdata, message):
    db = get_db()

    device_id = message.topic.split("/")[-1]
    payload = message.payload

    logging.info("payload = %s", payload)

    if payload.decode("utf8") == "on":
        with db:
            db.execute("UPDATE devices_table SET lights_on = 1 WHERE device_id IS (?)", device_id)
    elif payload.decode("utf8") == "off":
        with db:
            db.execute("UPDATE devices_table SET lights_on = 0 WHERE device_id IS (?)", device_id)


def get_client():
    mqtt_client = getattr(g, "_mqtt_client", None)

    if mqtt_client is None:
        mqtt_client = paho.Client(transport="websockets")
        mqtt_client.connect_async(host="broker", port=9001)
        mqtt_client.loop_start()
        mqtt_client.on_message = on_message_callback
        g._mqtt_client = mqtt_client

    return mqtt_client


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

        with db:
            try:
                db.execute("CREATE TABLE devices_table (device_id TEXT NOT NULL, lights_on INTEGER NOT NULL)")
            except:
                pass

    return db


@app.before_first_request
def setup_logging():
    log_cfg = """
version: 1
disable_existing_loggers: true
formatters:
    fluent_fmt:
        (): fluent.handler.FluentRecordFormatter
        format:
            level: '%(levelname)s'
            where: '%(filename)s.%(lineno)d'
handlers:
    fluent:
        class: fluent.handler.FluentHandler
        formatter: fluent_fmt
        tag: example
        port: 24224
        host: fluent
loggers:
    '':
        handlers:
            - fluent
        level: DEBUG
        propagate: true
"""

    as_dict = yaml.load(log_cfg)
    logging.config.dictConfig(as_dict)

    logging.info("Logging set up")


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

    try:
        mqtt_client = g._mqtt_client
    except AttributeError:
        pass
    else:
        mqtt_client.loop_stop()


@app.route("/send_mqtt_message", methods=["POST"])
def send_message():
    r = request.get_json()

    try:
        r["device_id"]
        r["payload"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key"}), 400

    mqtt_client = get_client()

    topic = "/device/{}".format(r["device_id"])

    try:
        logging.debug("Publishing '%s' on '%s'", r["payload"], topic)
        mqtt_client.publish(
            topic,
            r["payload"],
            r.get("qos", 0)
        )
    except Exception:
        return jsonify({"error": topic}), 500

    return jsonify({"topic": topic}), 200


@app.route("/get_device_state", methods=["GET"])
def get_device():
    r = request.args

    try:
        r["device_id"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key"}), 400

    db = get_db()

    with db:
        row = db.execute("SELECT * FROM devices_table WHERE device_id IS :device_id", r)

    try:
        status = next(row)[1]
    except StopIteration:
        with db:
            db.execute("INSERT INTO devices_table VALUES (:device_id, 0)", r)
            row = db.execute("SELECT * FROM devices_table WHERE device_id IS :device_id", r)
        status = next(row)[1]

    onoff = "on" if status else "off"

    return jsonify({"lights": onoff})


@app.route("/reset", methods=["POST"])
def reset_db():
    db = get_db()

    with db:
        db.execute("DELETE FROM numbers_table")

    return "", 204
