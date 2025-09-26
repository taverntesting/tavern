import dataclasses
import os.path
import random
import sys
from collections.abc import Mapping
from concurrent import futures
from typing import Any, Optional

import grpc
import pytest
from _pytest.mark import MarkGenerator
from google.protobuf import json_format
from google.protobuf.empty_pb2 import Empty
from grpc_reflection.v1alpha import reflection

from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc.client import GRPCClient
from tavern._plugins.grpc.request import GRPCRequest
from tavern._plugins.grpc.response import GRPCCode, GRPCResponse

sys.path.append(os.path.dirname(__file__))

from . import test_services_pb2, test_services_pb2_grpc


class ServiceImpl(test_services_pb2_grpc.DummyServiceServicer):
    def Empty(self, request: Empty, context) -> Empty:
        return Empty()

    def SimpleTest(
        self, request: test_services_pb2.DummyRequest, context: grpc.ServicerContext
    ) -> test_services_pb2.DummyResponse:
        if request.request_id > 1000:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "number too big!")
        return test_services_pb2.DummyResponse(response_id=request.request_id + 1)


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
        "attempt_reflection": False,
    }

    return GRPCClient(**opts)


@dataclasses.dataclass
class GRPCTestSpec:
    test_name: str
    method: str
    req: Any

    resp: Optional[Any] = None
    xfail: bool = False
    code: GRPCCode = grpc.StatusCode.OK.value[0]
    service: str = "tavern.tests.v1.DummyService"

    def service_method(self):
        return f"{self.service}/{self.method}"

    def request(self) -> Mapping:
        return json_format.MessageToDict(
            self.req,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
        )

    def body(self) -> Mapping:
        return json_format.MessageToDict(
            self.resp,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
        )


def test_grpc(grpc_client: GRPCClient, includes: TestConfig, test_spec: GRPCTestSpec):
    request = GRPCRequest(
        grpc_client,
        {"service": test_spec.service_method(), "body": test_spec.request()},
        includes,
    )

    expected = {"status": test_spec.code}
    if test_spec.resp:
        expected["body"] = test_spec.body()

    resp = GRPCResponse(grpc_client, "test", expected, includes)

    if test_spec.xfail:
        pytest.xfail()

    future = request.run()

    resp.verify(future)


def pytest_generate_tests(metafunc: MarkGenerator):
    if "test_spec" in metafunc.fixturenames:
        tests = [
            GRPCTestSpec(
                test_name="basic empty", method="Empty", req=Empty(), resp=Empty()
            ),
            GRPCTestSpec(
                test_name="nonexistent method",
                method="Wek",
                req=Empty(),
                resp=Empty(),
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="empty with numeric status code",
                method="Empty",
                req=Empty(),
                resp=Empty(),
                code=0,
            ),
            GRPCTestSpec(
                test_name="empty with wrong status code",
                method="Empty",
                req=Empty(),
                resp=Empty(),
                code="ABORTED",
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="empty with the wrong request type",
                method="Empty",
                req=test_services_pb2.DummyRequest(),
                resp=Empty(),
                code=0,
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="empty with the wrong response type",
                method="Empty",
                req=Empty(),
                resp=test_services_pb2.DummyResponse(),
                code=0,
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="Simple service",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=2),
                resp=test_services_pb2.DummyResponse(response_id=3),
            ),
            GRPCTestSpec(
                test_name="Simple service with error",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
            ),
            GRPCTestSpec(
                test_name="Simple service with error code but also a response",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                resp=test_services_pb2.DummyResponse(response_id=3),
                code="FAILED_PRECONDITION",
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="Simple service with wrong request type",
                method="SimpleTest",
                req=Empty(),
                resp=test_services_pb2.DummyResponse(response_id=3),
                xfail=True,
            ),
            GRPCTestSpec(
                test_name="Simple service with wrong response type",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=2),
                resp=Empty(),
                xfail=True,
            ),
        ]

        metafunc.parametrize("test_spec", tests, ids=[g.test_name for g in tests])
