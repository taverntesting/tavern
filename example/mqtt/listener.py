import json
import logging
import logging.config
import os
import sqlite3

import yaml
import paho.mqtt.client as paho


DATABASE = os.environ.get("DB_NAME")


def get_client():
    mqtt_client = paho.Client(transport="websockets", client_id="listener")
    mqtt_client.enable_logger()
    mqtt_client.connect_async(host="broker", port=9001)

    return mqtt_client


def get_db():
     return sqlite3.connect(DATABASE)


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
        tag: listener
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

    as_dict = yaml.load(log_cfg)
    logging.config.dictConfig(as_dict)

    logging.info("Logging set up")


def handle_lights_topic(message):
    db = get_db()

    device_id = message.topic.split("/")[-2]

    if message.payload.decode("utf8") == "on":
        logging.info("Lights have been turned on")
        with db:
            db.execute("UPDATE devices_table SET lights_on = 1 WHERE device_id IS (?)", (device_id,))
    elif message.payload.decode("utf8") == "off":
        logging.info("Lights have been turned off")
        with db:
            db.execute("UPDATE devices_table SET lights_on = 0 WHERE device_id IS (?)", (device_id,))

def handle_request_topic(client, message):
    db = get_db()

    device_id = message.topic.split("/")[-2]

    logging.info("Checking lights status")
    with db:
        row = db.execute("SELECT lights_on FROM devices_table WHERE device_id IS (?)", (device_id,))

    try:
        status = int(next(row)[0])
    except Exception:
        logging.exception("Error getting status for device '%s'", device_id)
    else:
        client.publish(
            "/device/{}/status/response".format(device_id),
            json.dumps({"lights": status})
        )


def handle_ping_topic(client, message):
    device_id = message.topic.split("/")[-2]

    client.publish(
        "/device/{}/pong".format(device_id),
        "pong",
    )


def on_message_callback(client, userdata, message):
    logging.info("Received message on %s", message.topic)

    if "lights" in message.topic:
        handle_lights_topic(message)
    elif "ping" in message.topic:
        handle_ping_topic(client, message)
    elif "status" in message.topic:
        handle_request_topic(client, message)
    else:
        logging.warning("Got unexpected MQTT topic '%s'", message.topic)


def wait_for_messages():
    setup_logging()
    mqtt_client = get_client()
    mqtt_client.on_message = on_message_callback
    mqtt_client.reconnect()

    topics = [
        "lights",
        "ping",
        "status",
    ]

    for t in topics:
        device_topic = "/device/{}/{}".format(123, t)
        logging.debug("Subscribing to '%s'", device_topic)
        mqtt_client.subscribe(device_topic)

    mqtt_client.loop_forever()


if __name__ == "__main__":
    db = get_db()

    with db:
        try:
            db.execute("CREATE TABLE devices_table (device_id TEXT NOT NULL, lights_on INTEGER NOT NULL)")
        except:
            pass

        try:
            db.execute("INSERT INTO devices_table VALUES ('123', 0)")
        except:
            pass

    wait_for_messages()
