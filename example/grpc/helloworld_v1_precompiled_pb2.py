# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: helloworld_v1_precompiled.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x1fhelloworld_v1_precompiled.proto\x12\rhelloworld.v1"\x1c\n\x0cHelloRequest\x12\x0c\n\x04name\x18\x01 \x01(\t"\x1d\n\nHelloReply\x12\x0f\n\x07message\x18\x01 \x01(\t2O\n\x07Greeter\x12\x44\n\x08SayHello\x12\x1b.helloworld.v1.HelloRequest\x1a\x19.helloworld.v1.HelloReply"\x00\x62\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "helloworld_v1_precompiled_pb2", _globals
)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _globals["_HELLOREQUEST"]._serialized_start = 50
    _globals["_HELLOREQUEST"]._serialized_end = 78
    _globals["_HELLOREPLY"]._serialized_start = 80
    _globals["_HELLOREPLY"]._serialized_end = 109
    _globals["_GREETER"]._serialized_start = 111
    _globals["_GREETER"]._serialized_end = 190
# @@protoc_insertion_point(module_scope)
