from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class DummyRequest(_message.Message):
    __slots__ = ["request_id"]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: int
    def __init__(self, request_id: _Optional[int] = ...) -> None: ...

class DummyResponse(_message.Message):
    __slots__ = ["response_id"]
    RESPONSE_ID_FIELD_NUMBER: _ClassVar[int]
    response_id: int
    def __init__(self, response_id: _Optional[int] = ...) -> None: ...
