import sqlite3
import os
import logging
import logging.config
import yaml


import paho.mqtt.client as paho


DATABASE = os.environ.get("DB_NAME")


def get_client():
    mqtt_client = paho.Client(transport="websockets")
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


def on_message_callback(client, userdata, message):
    db = get_db()

    device_id = message.topic.split("/")[-1]
    payload = message.payload

    logging.info("payload = %s", payload)

    if payload.decode("utf8") == "on":
        logging.info("Lights have been turned on")
        with db:
            db.execute("UPDATE devices_table SET lights_on = 1 WHERE device_id IS (?)", (device_id,))
    elif payload.decode("utf8") == "off":
        logging.info("Lights have been turned off")
        with db:
            db.execute("UPDATE devices_table SET lights_on = 0 WHERE device_id IS (?)", (device_id,))


def wait_for_messages():
    setup_logging()
    mqtt_client = get_client()
    mqtt_client.on_message = on_message_callback
    mqtt_client.reconnect()

    device_topic = "/device/{}/lights".format(123)

    logging.info("Subscribing to '%s'", device_topic)

    mqtt_client.subscribe(device_topic)

    mqtt_client.loop_forever()


if __name__ == "__main__":
    db = get_db()

    with db:
        try:
            db.execute("CREATE TABLE devices_table (device_id TEXT NOT NULL, lights_on INTEGER NOT NULL)")
        except:
            pass

    wait_for_messages()
