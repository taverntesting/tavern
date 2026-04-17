import logging
import os

from flask import Flask, Response, request
from google.protobuf.message import DecodeError
from tavern._plugins.grpc_web.codec import FLAG_TRAILER, decode_grpc_web_body, encode_data_frame

import helloworld_v1_precompiled_pb2 as helloworld_pb2

app = Flask(__name__)


def _encode_trailer_frame(*, grpc_status: str, grpc_message: str | None = None) -> bytes:
    trailer_lines = [f"grpc-status: {grpc_status}"]
    if grpc_message:
        trailer_lines.append(f"grpc-message: {grpc_message}")

    payload = ("\r\n".join(trailer_lines) + "\r\n").encode("utf-8")
    return bytes([FLAG_TRAILER]) + len(payload).to_bytes(4, byteorder="big") + payload


def _grpc_web_response(
    *,
    status: str,
    message_bytes: bytes | None = None,
    details: str | None = None,
) -> Response:
    body = b""
    if message_bytes is not None:
        body += encode_data_frame(message_bytes)
    body += _encode_trailer_frame(grpc_status=status, grpc_message=details)

    response = Response(body, status=200, content_type="application/grpc-web+proto")
    response.headers["x-grpc-web"] = "1"
    response.headers["grpc-status"] = status
    if details:
        response.headers["grpc-message"] = details
    return response


@app.post("/rpc/<path:rpc_path>")
def grpc_web_handler(rpc_path: str) -> Response:
    if rpc_path != "helloworld.v1.Greeter/SayHello":
        return _grpc_web_response(status="12", details="method not implemented")

    message_bytes, _ = decode_grpc_web_body(request.get_data() or b"")
    if message_bytes is None:
        return _grpc_web_response(status="3", details="empty request body")

    req = helloworld_pb2.HelloRequest()
    try:
        req.ParseFromString(message_bytes)
    except DecodeError:
        return _grpc_web_response(status="3", details="invalid protobuf payload")

    reply = helloworld_pb2.HelloReply(message=f"Hello, {req.name}!")
    return _grpc_web_response(status="0", message_bytes=reply.SerializeToString())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host=os.getenv("FLASK_HOST", "127.0.0.1"), port=50053)
