import dataclasses
import os.path
import random
import sys
from collections.abc import Generator, Mapping
from concurrent import futures
from typing import Any

import grpc
import pytest
from google.protobuf import json_format
from google.protobuf.empty_pb2 import Empty
from grpc_reflection.v1alpha import reflection
from pytest import MarkGenerator

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc.client import GRPCClient
from tavern._plugins.grpc.request import GRPCRequest
from tavern._plugins.grpc.response import GRPCCode, GRPCResponse, _to_grpc_name

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
def service() -> Generator[int, Any, None]:
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

    resp: Any | None = None
    expected_exception: type[Exception] | None = None
    code: GRPCCode = grpc.StatusCode.OK.value[0]
    # The status the server is actually expected to return - only needs setting
    # for tests which deliberately expect the 'wrong' status in 'code'
    actual_code: GRPCCode | None = None
    service: str = "tavern.tests.v1.DummyService"

    def actual_status_name(self) -> str:
        """Name of the grpc status the server should respond with"""
        name = _to_grpc_name(
            self.code if self.actual_code is None else self.actual_code
        )
        if not isinstance(name, str):
            raise ValueError("can only check a single expected status code")
        return name

    def service_method(self):
        return f"{self.service}/{self.method}"

    def request(self) -> Mapping:
        return json_format.MessageToDict(
            self.req,
            always_print_fields_with_no_presence=True,
            preserving_proto_field_name=True,
        )

    def body(self) -> Mapping:
        return json_format.MessageToDict(
            self.resp,
            always_print_fields_with_no_presence=True,
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

    if not test_spec.expected_exception:
        future = request.run()
        assert future.response.code().name == test_spec.actual_status_name()
        resp.verify(future)
        return

    # Some specs are expected to fail before the request is even sent, in which
    # case there is no status code to check
    try:
        future = request.run()
    except test_spec.expected_exception:
        return

    assert future.response.code().name == test_spec.actual_status_name()

    with pytest.raises(test_spec.expected_exception):
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
                expected_exception=exceptions.GRPCServiceException,
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
                actual_code="OK",
                expected_exception=exceptions.TestFailError,
            ),
            GRPCTestSpec(
                test_name="empty with the wrong request type",
                method="Empty",
                req=test_services_pb2.DummyRequest(),
                resp=Empty(),
                code=0,
                expected_exception=exceptions.GRPCRequestException,
            ),
            GRPCTestSpec(
                test_name="empty with the wrong response type",
                method="Empty",
                req=Empty(),
                resp=test_services_pb2.DummyResponse(),
                code=0,
                expected_exception=exceptions.TestFailError,
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
                expected_exception=exceptions.TestFailError,
            ),
            GRPCTestSpec(
                test_name="Simple service expecting a body but the request errors",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                resp=test_services_pb2.DummyResponse(response_id=3),
                actual_code="FAILED_PRECONDITION",
                expected_exception=exceptions.TestFailError,
            ),
            GRPCTestSpec(
                test_name="Simple service with wrong request type",
                method="SimpleTest",
                req=Empty(),
                resp=test_services_pb2.DummyResponse(response_id=3),
                expected_exception=exceptions.TestFailError,
            ),
            GRPCTestSpec(
                test_name="Simple service with wrong response type",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=2),
                resp=Empty(),
                expected_exception=exceptions.TestFailError,
            ),
        ]

        metafunc.parametrize("test_spec", tests, ids=[t.test_name for t in tests])
