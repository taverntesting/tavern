# gRPC integration testing

## Setting connection parameters

Testing using gRPC is similar to (mqtt)[mqtt.md],

There are 4 different types of service resolution:

#### Specifying the proto definition

#### Server reflection

This is obviously the least useful method. If you don't specify a proto source or module, the client
will attempt to
use [gRPC reflection](https://github.com/grpc/grpc/blob/master/doc/server-reflection.md) to
determine what is the appropriate message type for the message you're trying to send. This is not
reliable as the server you're trying to talk to might not have reflection turned on. 
