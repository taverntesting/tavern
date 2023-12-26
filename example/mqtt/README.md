# MQTT example

This has an even more complicated example of a web server and an MQTT 'listener'
that just reacts to MQTT messages, with a fluentd container to catch the Python
logs.

The listener waits for messages on `/device/<device_id>/lights` with a payload
of 'on' or 'off' and updates the database. It also listens on
`/device/<device_id>/ping` and responds with a message on
`/device/<device_id>/pong`.

The server queries this database when a `GET` request is made to
`/get_device_state` and returns whether the lights are on or off.

The tavern test file includes examples of how to test such a setup, using the
keys `mqtt_publish` and `mqtt_response`. Run `docker compose up --build` in one
terminal and run `py.test` in another terminal, and output from the mosquitto
MQTT broker, the server, and the listener will be shown inline.
