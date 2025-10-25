# GraphQL Subscriptions Support

## The Problem

There is support for sending GraphQL queries/mutations, but subscriptions are not yet supported.

Subscriptions work via WebSocket upgrade:
1. HTTP POST to `/graphql` with subscription query → server upgrades to WS (status **101 Switching Protocols**, no data body).
2. Client sends `Connection_init`, then `Start` (with payload/query).
3. Server sends `Data`, `Complete`, `Error` over WS (graphql-ws protocol: https://github.com/enisdenjo/graphql-ws).
4. Use **sync** `websocket-client` library (not async `websockets`) to avoid asyncio.

Example flow in Tavern YAML:

There is support for sending graphql queries, but subscriptions are not yet supported.

The way this would probably work is that a user would first make a `graphql_query` with a 'subscription' type like

```yaml
stages:
  - name: subscribe to user
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        subscription GetUser($id: ID!) {
          user(id: $id) {
            id
            name
            email
          }
        }
      variables:
        id: "1"
```

Then future stages would have a `graphql_response` which might be in response to a HTTP request, the same way that mqtt
responses currently work. MQTT example:

```yaml
stages:
  - name: step 1 - post message trigger
    # HTTP request
    request:
      url: "{host}/send_mqtt_message"
      json:
        device_id: "{random_device_id}"
        payload: "hello"
      method: POST
      headers:
        content-type: application/json
    # HTTP response
    response:
      status_code: 200
      json:
        topic: "/device/{random_device_id}"
      headers:
        content-type: application/json
    # ALSO an MQTT response
    mqtt_response:
      topic: /device/{random_device_id}
      payload: "hello"
      timeout: 5
```

For graphql, this would be like:

```yaml
stages:
  - name: step 1 - subscribe to user
    # ... As above
  - name: step 2 - post message and expect subscription response
    # HTTP request
    request:
      url: "{host}/update_user"
      json:
        name: "Alice Johnson"
        email: "alice@example.com"
      method: POST
      headers:
        content-type: application/json
    # HTTP response
    response:
      status_code: 200
      headers:
        content-type: application/json
    # ALSO a graphql response, triggered by the subscription
    graphql_response:
      json:
        data:
          user:
            id: "1"
            name: "Alice Johnson"
            email: "alice@example.com"
```

Or if a user makes a graphql request triggers a normal HTTP response from the query and a response from the
subscription:

```yaml
stages:
  - name: step 1 - subscribe to user
    # ... As above
  - name: step 2 - post message and expect two graphql responses
    # graphQL request mutation
    graphql_request:
      url: "{graphql_server_url}/graphql"
      query: |
        mutation UpdateUser($name: String!, $email: String!) {
          updateUser(name: $name, email: $email) {
            id
            name
            email
          }
        }
      variables:
        name: "Alice Johnson"
        email: "alice@example.com"
    # One graphql response from the query, one from the subscription (silly example)
    graphql_response:
      - json:
          data:
            user:
              id: "1"
              name: "Alice Johnson"
              email: "alice@example.com"
      - json:
          data:
            user:
              id: "1"
              name: "Alice Johnson"
              email: "alice@example.com"
```

Perhaps there should be a way to indicate for each graphql_response which subscription it is for. For the above example
where the subcription is `subscription GetUser(...)`, this might be:

```yaml
    graphql_response:
      # From the subscription
      - subscription: GetUser
        json:
          data:
            user:
              id: "1"
              name: "Alice Johnson"
              email: "alice@example.com"
      # From the query
      - json:
          data:
            user:
              id: "1"
              name: "Alice Johnson"
              email: "alice@example.com"
```

The flow is:

1. User makes a `subscription` graphql request and expects 200 back
2. User makes a request in a future stage (which might be a http request, or an mqtt request, or a graphql
   request) and expects the response from that and possibly the response from the subscription. This might result in two
   `graphql_response`s, or a `response` and a `graphql_response` like above.

## Code changes

- Update `GraphQLClient` (tavern/_plugins/graphql/client.py) to support graphql-ws over sync WS:
  - On subscription `graphql_request`: POST HTTP, expect 101, upgrade to WS w/ websocket-client.
  - Track active subs by operation name/hash (dict of queues for responses).
  - No per-stage session; persist WS across test run.
  - On `graphql_response`: pop/dequeue from matching sub queue, match JSON.
- Update JSON schema (tavern/schemas/plugins/graphql_request.json etc.) for `type: subscription` (optional, auto-detect from query).
- Update entrypoint (tavern/_plugins/graphql/tavernhook.py) to handle `graphql_response` like MQTT (poll/dequeue WS msgs).
  with `graphql_request`, it needs to also track susbcriptions _for the duration of a test_, not just the duration of
  the stage. This should create a websocket connection using the websockets library.
- This should also handle multiple subscriptions at once.
- json schema in the graphql plugin needs to be updated to support subscriptions.
- Update the graphql tavern entrypoint so it can handle multiple responses like in tavern/_plugins/mqtt/tavernhook.py.

Use sync `websocket-client` (add to pyproject.toml optional-deps.graphql if needed).

After this, update the example server in example/graphql/server.py to have subscriptions, and add integration tests
using those subscriptions alongside the existing tests in example/graphql/.