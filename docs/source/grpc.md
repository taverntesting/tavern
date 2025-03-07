# gRPC integration testing

## Current limitations / future plans

- Should be able to specify channel credentials.
- Currently there is no way of doing custom TLS options (like with rest/mqtt)
- Better syntax around importing modules
- Some way of representing streaming RPCs? This is pretty niche and Tavern is built around a core of only making 1
  request which doesn't work well with streaming request RPCs, but streaming response RPCs could be handled like
  multiple MQTT responses.
- Much like the tavern-flask plugin it wouldn't be too difficult to write a plugin which started a Python gRPC server
  in-process and ran tests against that instead of having to use a remote server
- Fix comparing results - currently it serialises with

      including_default_value_fields=True,
      preserving_proto_field_name=True,

  Which formats a field like `my_field_name` as `my_field_name` and not `myFieldName` which is what protojson in Go
  converts it to for example, need to provide a way to allow people to write tests using either one
- protos are compiled into a folder based on `tempfile.gettempdir()`, this could be configurable

## Connection

There are 2 ways of specifying the grpc connection, in the `grpc` block at the top of the test similarly to an mqtt
connection block, or in the test stage itself.

In the `grpc.connect` block:

```yaml
grpc:
  connect:
    host: localhost
    port: 50052
```

In the test stage itself:

```yaml
stages:
  - name: Do a thing
    grpc_request:
      host: "localhost: 50052"
      service: my.cool.service/Waoh
      body:
        ...
```

The connection will be established at the beginning of the test and dropped when it finishes.

### SSL connection

Tavern currently _defaults to an insecure connection_ when connecting to grpc, to enable SSL connections add
the `secure` key in the `connect` block:

```yaml
grpc:
  connect:
    secure: true
```

### Metadata

Generic metadata can be passed on every message using the `metadata` key:

```yaml
grpc:
  metadata:
    my-extra-info: something
```

### Advanced: connection options

Generic connection options can be passed as key:value pairs under the `options` block:

```yaml
grpc:
  connect:
    options:
      grpc.max_send_message_length: 10000000
```

See [the gRPC documentation](https://grpc.github.io/grpc/core/group__grpc__arg__keys.html) for a list of possible
options, note that some of these may not be implemented in Python.

## Requests

The `grpc_request` block requires, at minimum, the name of the service to send the request to

```yaml
stages:
  - name: Say hello
    grpc_request:
      service: helloworld.v3.Greeter/SayHello
      body:
        name: "John"
```

The 'body' block will be reflected into the protobuf message type expected for the service, if the schema is invalid
then an exception will be raised.

## Responses

If no response is specified, Tavern will assume that _any_ response with an `OK` status code to be successful.

Other status codes are specified using the `status` key. The gRPC status code should be a string matching
a [gRPC status code](https://grpc.github.io/grpc/core/md_doc_statuscodes.html), for
example `OK`, `NOT_FOUND`, etc. or the numerical value of the code. It can also be a list of codes.

```yaml
stages:
  - name: Echo text
    grpc_request:
      service: helloworld.v1.Greeter/SayHello
      body:
        name: "John"
    grpc_response:
      status: "OK"  # Also the default
```

## Loading protobuf definitions

There are 3 different ways Tavern will try to load the appropriate proto definitions:

#### Specifying the proto module to use

If you already have all the Python gRPC stubs in your repository. Example:

```yaml
grpc:
  proto:
    module: server/helloworld_pb2_grpc
```

This will attempt to import the given module (it should not be a Python file, but the path to the module containing the
existing stubs) and register all the protos in it.

#### Specifying a folder with some protos in

Example:

```yaml
grpc:
  proto:
    source: path/to/protos
```

This will attempt to find all files ending in `.proto` in the given folder and compile them using
the protoc compiler. It first checks the value of the environment variable `PROTOC` and use that,
and if not defined it will then look for a binary called `protoc` in the path. proto files are
compiled into a folder called `proto` under the same folder that the Tavern yaml is in.

This has a few drawbacks, especially that if it can't find the protoc compiler at runtime it will
fail, but it might be useful if you're talking to a Java/Go/other server and you don't want to keep
some compiled Python gRPC stubs in your repository.

The main downside to this is that Tavern currently depends on `protobuf>=4,<5`. If the version of 
`protoc` you are using generates outputs that are incompatible with this, it will fail at runtime. 
Consider using this only as a last resort!

#### Server reflection

This is obviously the least useful method. If you don't specify a proto source or module, the client
can attempt to
use [gRPC reflection](https://github.com/grpc/grpc/blob/master/doc/server-reflection.md) to
determine what is the appropriate message type for the message you're trying to send. This is not
reliable as the server you're trying to talk to might not have reflection turned on. This needs to be specified in
the `grpc` block:

```yaml
grpc:
  attempt_reflection: true
```
