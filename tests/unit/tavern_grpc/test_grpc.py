import os.path
import random
import sys
from concurrent import futures

import grpc
import pytest
from google.protobuf.empty_pb2 import Empty

sys.path.append(os.path.dirname(__file__))

from . import test_services_pb2, test_services_pb2_grpc


class ServiceImpl(test_services_pb2_grpc.DummyServiceServicer):
    def Empty(self, request: Empty, context) -> Empty:
        return Empty()

    def SimpleTest(
        self, request: test_services_pb2.DummyRequest, context: grpc.ServicerContext
    ) -> test_services_pb2.DummyResponse:
        if request.id > 1000:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "number too big!")
        return test_services_pb2.DummyResponse(id=request.id)


@pytest.fixture(scope="session")
def service():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    service_impl = ServiceImpl()
    test_services_pb2_grpc.add_DummyServiceServicer_to_server(service_impl, server)
    port = random.randint(10000, 40000)
    address = f"127.0.0.1:{port}"
    server.add_insecure_port(address)
    server.start()

    yield address

    server.stop(1)


def test_server_empty(service):
    pass
