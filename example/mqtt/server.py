import contextlib
import logging
import logging.config
import os
import sqlite3

import paho.mqtt.client as paho
import yaml
from flask import Flask, g, jsonify, request

app = Flask(__name__)
application = app

DATABASE = os.environ.get("DB_NAME")


@contextlib.contextmanager
def get_client():
    mqtt_client = paho.Client(transport="websockets", client_id="server")
    mqtt_client.enable_logger()
    mqtt_client.username_pw_set(username="tavern", password="tavern")

    mqtt_client.connect(host="broker", port=9001)

    try:
        mqtt_client.loop_start()
        yield mqtt_client
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()


def get_db():
    return sqlite3.connect(DATABASE)


def get_cached_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = get_db()

    return db


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
        tag: server
        port: 24224
        host: fluent
loggers:
    paho:
        handlers:
            - fluent
        level: DEBUG
        propagate: true
    '':
        handlers:
            - fluent
        level: DEBUG
        propagate: true
"""

    as_dict = yaml.load(log_cfg, Loader=yaml.SafeLoader)
    logging.config.dictConfig(as_dict)

    logging.info("Logging set up")


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.route("/send_mqtt_message", methods=["POST"])
def send_message():
    r = request.get_json()

    try:
        r["device_id"]
        r["payload"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key"}), 400

    topic = "/device/{}".format(r["device_id"])

    logging.debug("Publishing '%s' on '%s'", r["payload"], topic)

    try:
        with get_client() as mqtt_client:
            mqtt_client.publish(topic, r["payload"], r.get("qos", 0))
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

    db = get_cached_db()

    with db:
        row = db.execute("SELECT * FROM devices_table WHERE device_id IS :device_id", r)

    try:
        status = next(row)[1]
    except StopIteration:
        return (
            jsonify(
                {"error": "could not find device with id {}".format(r["device_id"])}
            ),
            400,
        )

    onoff = "on" if status else "off"

    logging.info("Lights are %s", onoff)

    return jsonify({"lights": onoff})


@app.route("/create_device", methods=["PUT"])
def create_device():
    r = request.get_json(force=True)
    logging.error(r)

    try:
        r["device_id"]
    except (KeyError, TypeError):
        return jsonify({"error": "missing key device_id"}), 400

    db = get_cached_db()
    with db:
        row = db.execute(
            "SELECT device_id from devices_table where device_id is :device_id", r
        )

    try:
        r["clean"]
    except (TypeError):
        return jsonify({"error": "checking for clean key"}), 500
    except KeyError:
        try:
            next(row)
        except StopIteration:
            pass
        else:
            return jsonify({"error": "device already exists"}), 400
    else:
        with db:
            db.execute("DELETE FROM devices_table")

    new_device = dict(lights_on=False, **r)

    logging.info("Creating new device: %s", new_device)

    with db:
        db.execute(
            "INSERT INTO devices_table (device_id, lights_on) VALUES (:device_id, :lights_on)",
            new_device,
        )

    return jsonify({"status": "created device {device_id}".format(**r)}), 201


@app.route("/reset", methods=["POST"])
def reset_db():
    db = get_cached_db()
    return _reset_db(db)


def _reset_db(db):
    with db:

        def attempt(query):
            with contextlib.suppress(Exception):
                db.execute(query)


        attempt("DELETE FROM devices_table")
        attempt(
            "CREATE TABLE devices_table (device_id TEXT NOT NULL, lights_on INTEGER NOT NULL)"
        )

    return "", 204


if __name__ == "__main__":
    setup_logging()
    db = get_db()
    _reset_db(db)
