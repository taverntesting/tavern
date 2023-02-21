# MQTT integration testing

## Testing with MQTT messages

Since version `0.4.0` Tavern has supported tests that require sending and
receiving MQTT messages.

This is a very simple MQTT test that only uses MQTT messages:

```yaml
# test_mqtt.tavern.yaml
---

test_name: Test mqtt message response
paho-mqtt:
  client:
    transport: websockets
    client_id: tavern-tester
  connect:
    host: localhost
    port: 9001
    timeout: 3

stages:
  - name: step 1 - ping/pong
    mqtt_publish:
      topic: /device/123/ping
      payload: ping
    mqtt_response:
      topic: /device/123/pong
      payload: pong
      timeout: 5
```

The first thing to notice is the extra `paho-mqtt` block required at the top level.
When this block is present, an MQTT client will be started for the current test
and is used to publish and receive messages from a broker.

### MQTT connection options

The MQTT library used is the
[paho-mqtt](https://github.com/eclipse/paho.mqtt.python) Python library, and for
the most part the arguments for each block are passed directly through to the
similarly-named methods on the `paho.mqtt.client.Client` class.

The full list of options for the `mqtt` client block are listed below (`host`
is the only required key, though you will almost always require some of the
others):

- `client`: Passed through to `Client.__init__`.
  - `transport`: Connection type, optional. `websockets` or `tcp`. Defaults to
    `tcp`.
  - `client_id`: MQTT client ID, optional. Defaults to `tavern-tester`.
  - `clean_session`: Whether to connect with a clean session or not. `true` or
    `false`. Defaults to `false`.
- `connect`: Passed through to `Client.connect`.
  - `host`: MQTT broker host.
  - `port`: MQTT broker port. Defaults to 1883 in the paho-mqtt library.
  - `keepalive`: Keepalive frequency to MQTT broker. Defaults to 60 (seconds) in
    the paho-mqtt library. Note that some brokers will kick client off after 60
    seconds by default (eg VerneMQ), so you might need to lower this if you are
    kicked off frequently.
  - `timeout`: How many seconds to try and connect to the MQTT broker before giving up.
    This is not passed through to paho-mqtt, it is implemented in Tavern.
    Defaults to 1.
- `tls`: Controls TLS connection - as well as `enable`, this accepts all
  keywords taken by `Client.tls_set()` (see
  [paho documentation](https://github.com/eclipse/paho.mqtt.python/blob/e9914a759f9f5b8081d59fd65edfd18d229a399e/src/paho/mqtt/client.py#L636-L671)
  for the meaning of these keywords).
  - `enable`: Enable TLS connection with broker. If no other `tls` options are
    passed, using `enable: true` will enable tls without any custom
    certificates/keys/ciphers. If `enable: false` is used, any other tls options
    will be ignored.
  - `ca_certs`
  - `certfile`
  - `keyfile`
  - `cert_reqs`
  - `tls_version`
  - `ciphers`
- `auth`: Passed through to `Client.username_pw_set`.
  - `username`: Username to connect to broker with.
  - `password`: Password to use with username.

The above example connects to an MQTT broker on port 9001 using the websockets
protocol, and will try to connect for 3 seconds before failing the test.

Similar to the persistent `requests` session, the MQTT client is created at the
beginning of a test and used for all stages in the test.

### MQTT publishing options

Messages can be published using the MQTT broker with the `mqtt_publish` key. In
the above example, a message is published on the topic `/device/123/ping`, with
the payload `ping`.

Like when making HTTP requests, JSON can be sent using the `json` key instead of
the `payload` key.

```yaml
    mqtt_publish:
      topic: /device/123/ping
      json:
        thing_1: abc
        thing_2: 123
```

This will result in the MQTT payload `'{"thing_2": 123, "thing_1": "abc"}'`
being sent.

The full list of keys for this block:

- `topic`: The MQTT topic to publish on
- `payload` OR `json`: A plain text payload to publish, or a YAML object to
  serialize into JSON.
- `qos`: QoS level for publishing. Defaults to 0 in paho-mqtt.

### Options for receiving MQTT messages

The `mqtt_response` key gives a topic and payload which should be received by
the end of the test stage, or that stage will be considered a failure. This
works by subscribing to the topic specified before running the test, and then
waiting after the test for a specified timeout for that message to be sent. If a
message on the topic specified with **the same payload** is not received within
that timeout period, it is considered a failure.

If other messages on the same topic but with a different payload arrive in the
meantime, they are ignored and a warning will be logged.

```yaml
    mqtt_response:
      topic: /device/123/ping
      json:
        thing_1: abc
        thing_2: 123
```

The keys which can be used:

- `topic`: The MQTT topic to subcribe to
- `payload` OR `json`: A plain text payload or a YAML object that will be
  serialized into JSON that must match the payload of a message published to
  `topic`.
- `timeout`: How many seconds to wait for the message to arrive. Defaults to 3.
- `qos`: The level of QoS to subscribe to the topic with. This defaults to 1,
  and it is unlikely that you will need to ever set this value manually.

While the `json` key will follow the same matching rules as
HTTP JSON responses, The special 'anything' token can be used with the
`payload` key just to check that there was _some_ response on a topic:

```yaml
    mqtt_response:
      topic: /device/123/ping
      payload: !anything
```

Other type tokens such as `!anyint` will _not_ work.

### Unexpected messages

If you want to make sure that you do _not_ want to receive a message when a certain request (MQTT or
HTTP) is sent, use the 'unexpected' key like so:

```yaml
  mqtt_response:
    topic: /device/123/status/response
    payload: !anything
    timeout: 3
    qos: 1
    unexpected: true
```

If this message is received during the test, it will fail it. Be careful when using this as if this
message just happened to be sent during the test and not as a result of anything during your test,
it will still make the test fail.

## Mixing MQTT tests and HTTP tests

If the architecture of your program combines MQTT and HTTP, Tavern can
seamlessly test either or both of them in the same test, and even in the same
stage.

### MQTT messages in separate stages

In this example we have a server that listens for an MQTT message from a device
for it to say that a light has been turned on. When it receives this message, it
updates a database so that each future request to get the state of the device
will return the updated state.

```yaml
---

test_name: Make sure posting publishes mqtt message

includes:
  - !include common.yaml

# More realistic broker connection options
paho-mqtt: &mqtt_spec
  client:
    transport: websockets
  connect:
    host: an.mqtt.broker.com
    port: 4687
  tls:
    enable: true
  auth:
    username: joebloggs
    password: password123

stages:
  - name: step 1 - get device state with lights off
    request:
      url: "{host}/get_device_state"
      params:
        device_id: 123
      method: GET
      headers:
        content-type: application/json
    response:
      status_code: 200
      json:
        lights: "off"
      headers:
        content-type: application/json

  - name: step 2 - publish an mqtt message saying that the lights are now on
    mqtt_publish:
      topic: /device/123/lights
      qos: 1
      payload: "on"
    delay_after: 2

  - name: step 3 - get device state, lights now on
    request:
      url: "{host}/get_device_state"
      params:
        device_id: 123
      method: GET
      headers:
        content-type: application/json
    response:
      status_code: 200
      json:
        lights: "on"
      headers:
        content-type: application/json
```

You can see from this example that when using `mqtt_publish` we don't
necessarily need to expect a message to be published in return - We can just
send a message and wait for it to be processed with `delay_after`.

### MQTT message in the same stage

MQTT blocks and HTTP blocks can be combined in the same test stage to test that
sending a HTTP request results in an MQTT message being sent.

Say we have a server that takes a device id and publishes an MQTT message to it
saying hello:

```yaml
---

test_name: Make sure posting publishes mqtt message

includes:
  - !include common.yaml

paho-mqtt: *mqtt_spec

stages:
  - name: step 1 - post message trigger
    request:
      url: "{host}/send_mqtt_message"
      json:
        device_id: 123
        payload: "hello"
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      json:
        topic: "/device/123"
      headers:
        content-type: application/json
    mqtt_response:
      topic: /device/123
      payload: "hello"
      timeout: 5
      qos: 2
```

Before running the `request` in this stage, Tavern will subscribe to
`/device/123` with QoS level 2. After making the request (and getting the
correct response from the server!), it will wait 5 seconds for a message to be
published on that topic.

**Note**: You can only have one of `request` or `mqtt_publish` in a test stage.
If you need to publish a message and send a HTTP request in sequence, use an
approach like the previous example where they are in two separate stages.
