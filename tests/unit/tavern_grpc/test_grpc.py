import dataclasses
import os.path
import random
import re
import sys
from collections.abc import Generator, Mapping
from concurrent import futures
from typing import Any

import grpc
import pytest
from google.protobuf import any_pb2, json_format
from google.protobuf.empty_pb2 import Empty
from google.rpc import code_pb2, error_details_pb2, status_pb2
from grpc_reflection.v1alpha import reflection
from grpc_status import rpc_status
from pytest import MarkGenerator

from tavern._core import exceptions
from tavern._core.loader import _RegexSearchSentinel
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
            # Aborting with a google.rpc.Status attaches 'rich' error details to the response as
            # well as the plain details string
            packed = any_pb2.Any()
            packed.Pack(
                error_details_pb2.BadRequest(
                    field_violations=[
                        error_details_pb2.BadRequest.FieldViolation(
                            field="request_id", description="number too big!"
                        )
                    ]
                )
            )
            context.abort_with_status(
                rpc_status.to_status(
                    status_pb2.Status(
                        code=code_pb2.FAILED_PRECONDITION,
                        message="number too big!",
                        details=[packed],
                    )
                )
            )
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
class GRPCRequestSpec:
    """A request which is invalid, so it fails before anything is sent to the server"""

    test_name: str
    method: str
    req: Any

    expected_exception: type[Exception] = exceptions.GRPCRequestException
    service: str = "tavern.tests.v1.DummyService"

    def service_method(self) -> str:
        return f"{self.service}/{self.method}"

    def request(self) -> Mapping:
        return json_format.MessageToDict(
            self.req,
            always_print_fields_with_no_presence=True,
            preserving_proto_field_name=True,
        )


@dataclasses.dataclass
class GRPCTestSpec:
    """A request which is sent to the server, and the response checked against 'expected'"""

    test_name: str
    method: str
    req: Any

    resp: Any | None = None
    # Expected error message on the response - a string, or a sentinel matching one
    error_message: Any | None = None
    # Expected error details attached to the response
    details: Any | None = None
    expected_exception: type[Exception] | None = None
    # Substring which should be in the exception raised, to check the test failed for
    # the reason it was supposed to
    expected_exception_message: str | None = None
    code: GRPCCode = grpc.StatusCode.OK.value[0]
    service: str = "tavern.tests.v1.DummyService"

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


def test_grpc_bad_request(
    grpc_client: GRPCClient, includes: TestConfig, request_spec: GRPCRequestSpec
):
    """A request which doesn't match the service definition never reaches the server"""
    request = GRPCRequest(
        grpc_client,
        {"service": request_spec.service_method(), "body": request_spec.request()},
        includes,
    )

    with pytest.raises(request_spec.expected_exception):
        request.run()


def test_grpc(grpc_client: GRPCClient, includes: TestConfig, test_spec: GRPCTestSpec):
    """The response from the server is checked against the expected response block"""
    request = GRPCRequest(
        grpc_client,
        {"service": test_spec.service_method(), "body": test_spec.request()},
        includes,
    )

    expected: dict[str, Any] = {"status": test_spec.code}
    if test_spec.resp:
        expected["body"] = test_spec.body()
    if test_spec.error_message is not None:
        expected["error_message"] = test_spec.error_message
    if test_spec.details is not None:
        expected["details"] = test_spec.details

    resp = GRPCResponse(grpc_client, "test", expected, includes)

    future = request.run()

    if not test_spec.expected_exception:
        assert future.response.code().name == _to_grpc_name(test_spec.code)
        resp.verify(future)
        return

    match = (
        re.escape(test_spec.expected_exception_message)
        if test_spec.expected_exception_message
        else None
    )
    with pytest.raises(test_spec.expected_exception, match=match):
        resp.verify(future)


def pytest_generate_tests(metafunc: MarkGenerator):
    if "request_spec" in metafunc.fixturenames:
        requests = [
            GRPCRequestSpec(
                test_name="nonexistent method",
                method="Wek",
                req=Empty(),
                expected_exception=exceptions.GRPCServiceException,
            ),
            GRPCRequestSpec(
                test_name="the wrong request type",
                method="Empty",
                req=test_services_pb2.DummyRequest(),
            ),
        ]

        metafunc.parametrize(
            "request_spec", requests, ids=[t.test_name for t in requests]
        )

    if "test_spec" in metafunc.fixturenames:
        tests = [
            GRPCTestSpec(
                test_name="basic empty", method="Empty", req=Empty(), resp=Empty()
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
                expected_exception=exceptions.TestFailError,
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
                test_name="Simple service with error and matching error message",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
                error_message="number too big!",
            ),
            GRPCTestSpec(
                test_name="Simple service with error message matching a regex",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
                error_message=_RegexSearchSentinel(re.compile("too big")),
            ),
            GRPCTestSpec(
                test_name="Simple service with error and the wrong error message",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
                error_message="number too small!",
                expected_exception=exceptions.TestFailError,
            ),
            GRPCTestSpec(
                test_name="Simple service with error and matching details",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
                details=[
                    {
                        "@type": "type.googleapis.com/google.rpc.BadRequest",
                        "field_violations": [
                            {"field": "request_id", "description": "number too big!"}
                        ],
                    }
                ],
            ),
            GRPCTestSpec(
                test_name="Simple service with error and the wrong details",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=10000),
                code="FAILED_PRECONDITION",
                details=[
                    {
                        "@type": "type.googleapis.com/google.rpc.BadRequest",
                        "field_violations": [
                            {"field": "request_id", "description": "number too small!"}
                        ],
                    }
                ],
                expected_exception=exceptions.TestFailError,
                error_message="number too small!",
            ),
            GRPCTestSpec(
                test_name="Simple service expecting details but there are none",
                method="SimpleTest",
                req=test_services_pb2.DummyRequest(request_id=2),
                resp=test_services_pb2.DummyResponse(response_id=3),
                details=[
                    {"@type": "type.googleapis.com/google.rpc.BadRequest"},
                ],
                expected_exception=exceptions.TestFailError,
                expected_exception_message="expected error details",
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
