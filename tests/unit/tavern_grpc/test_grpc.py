import os.path
import random
import sys
from concurrent import futures

import grpc
import pytest
from google.protobuf.empty_pb2 import Empty
from google.protobuf.json_format import MessageToDict
from grpc_reflection.v1alpha import reflection

from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc.client import GRPCClient
from tavern._plugins.grpc.request import GRPCRequest
from tavern._plugins.grpc.response import GRPCResponse

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
def service() -> int:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    service_impl = ServiceImpl()
    test_services_pb2_grpc.add_DummyServiceServicer_to_server(service_impl, server)

    service_names = (
        test_services_pb2.DESCRIPTOR.services_by_name["DummyService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    port = random.randint(10000, 40000)
    server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()

    yield port

    server.stop(1)


@pytest.fixture()
def grpc_client(service: int) -> GRPCClient:
    opts = {
        "connect": {"host": "localhost", "port": service, "secure": False},
        "attempt_reflection": True,
    }

    return GRPCClient(**opts)


def wrap_make_request(
    client: GRPCClient, service_name: str, req, resp, test_block_config: TestConfig
):
    request = GRPCRequest(
        client, {"service": service_name, "body": MessageToDict(req)}, test_block_config
    )

    future = request.run()

    resp_as_dict = MessageToDict(resp)

    resp = GRPCResponse(client, "test", resp_as_dict, test_block_config)

    resp.verify(future)


def test_server_empty(grpc_client, includes):
    wrap_make_request(
        grpc_client, "tavern.tests.v1.DummyService/Empty", Empty(), Empty(), includes
    )
