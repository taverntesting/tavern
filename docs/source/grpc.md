# gRPC integration testing

## Responses

The gRPC status code should be a string matching
a [gRPC status code](https://grpc.github.io/grpc/core/md_doc_statuscodes.html), for
example `OK`, `NOT_FOUND`, etc.

## Loading protobuf definitions

There are 3 different ways Tavern will try to load the appropriate proto definitions:

#### Specifying the proto module to use

Example:

```yaml
grpc:
  proto:
    module: server/helloworld_pb2_grpc
```

This will attempt to import the given module and register all the protos in it.

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

#### Server reflection

This is obviously the least useful method. If you don't specify a proto source or module, the client
will attempt to
use [gRPC reflection](https://github.com/grpc/grpc/blob/master/doc/server-reflection.md) to
determine what is the appropriate message type for the message you're trying to send. This is not
reliable as the server you're trying to talk to might not have reflection turned on. 
