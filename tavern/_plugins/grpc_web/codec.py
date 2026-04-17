from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

FLAG_DATA = 0x00
FLAG_TRAILER = 0x80


def encode_data_frame(message_bytes: bytes) -> bytes:
    flags = bytes([FLAG_DATA])
    length = len(message_bytes).to_bytes(4, byteorder="big")
    return flags + length + message_bytes


def decode_grpc_web_body(data: bytes) -> tuple[bytes | None, dict[str, str]]:
    trailers: dict[str, str] = {}
    message_bytes: bytes | None = None
    offset = 0
    while offset + 5 <= len(data):
        flag = data[offset]
        length = int.from_bytes(data[offset + 1: offset + 5], byteorder="big")
        offset += 5
        if offset + length > len(data):
            logger.warning(
                "Frame length (%s) exceeds remaining buffer (%s bytes)",
                length,
                len(data) - offset,
            )
            break

        chunk = data[offset: offset + length]
        offset += length
        # gRPC-Web uses the MSB of the frame flag: 1=trailers, 0=data
        if flag & FLAG_TRAILER:
            for line in chunk.decode("utf-8", errors="replace").split("\r\n"):
                if not line or ":" not in line:
                    continue

                key, _, value = line.partition(":")
                trailers[key.strip().lower()] = value.strip()
        else:
            # Unary calls are expected here, so we keep the first data frame
            if message_bytes is None:
                message_bytes = chunk

    return message_bytes, trailers
