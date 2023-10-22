import functools
import logging
import os
import pkgutil
import subprocess
import sys
import warnings
from distutils.spawn import find_executable
from importlib import import_module
from typing import Mapping, Optional

import grpc
import grpc_reflection
from google.protobuf import descriptor_pb2, json_format, message_factory
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.json_format import ParseError
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
from grpc_status import rpc_status

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys

logger = logging.getLogger(__name__)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    warnings.warn("deprecated", DeprecationWarning)  # noqa: B028


@functools.lru_cache
def find_protoc() -> str:
    # Find the Protocol Compiler.
    if "PROTOC" in os.environ and os.path.exists(os.environ["PROTOC"]):
        return os.environ["PROTOC"]

    if protoc := find_executable("protoc"):
        return protoc

    raise exceptions.ProtoCompilerException(
        "Wanted to dynamically compile a proto source, but could not find protoc"
    )


@functools.lru_cache
def _generate_proto_import(source: str, output: str):
    """Invokes the Protocol Compiler to generate a _pb2.py from the given
    .proto file.  Does nothing if the output already exists and is newer than
    the input."""

    if not os.path.exists(source):
        raise exceptions.ProtoCompilerException(
            "Can't find required file: {}".format(source)
        )

    if not os.path.exists(output):
        os.makedirs(output)

    logger.info("Generating %s...", output)
    protos = [
        os.path.join(source, child)
        for child in os.listdir(source)
        if (not os.path.isdir(child)) and child.endswith(".proto")
    ]

    if not protos:
        raise exceptions.ProtoCompilerException(
            f"No protos defined in {os.path.abspath(source)}"
        )

    protoc = find_protoc()

    protoc_command = [protoc, "-I" + source, "--python_out=" + output]
    protoc_command.extend(protos)

    call = subprocess.run(protoc_command, capture_output=True)  # noqa: S603
    if call.returncode != 0:
        logger.error(f"Error calling '{protoc_command}'")
        raise exceptions.ProtoCompilerException(call.stderr.decode("utf8"))

    logger.info(f"Generated module from protos: {protos}")


def _import_grpc_module(output: str):
    output_path = []

    py_module = output + ".py"
    if os.path.exists(py_module):
        output_path.append(py_module)
    else:
        mod = import_module(output)
        output_path.extend(mod.__name__)

    sys.path.extend(output_path)
    for _, name, _ in pkgutil.iter_modules(output_path):
        import_module("." + name, package=output)


class GRPCClient:
    def __init__(self, **kwargs):
        logger.debug("Initialising GRPC client with %s", kwargs)
        expected_blocks = {
            "connect": {"host", "port", "options", "compression", "timeout", "tls"},
            "proto": {"source", "module"},
            "metadata": {},
            "attempt_reflection": {},
        }
        # check main block first
        check_expected_keys(expected_blocks.keys(), kwargs)

        _connect_args = kwargs.pop("connect", {})
        check_expected_keys(expected_blocks["connect"], _connect_args)

        metadata = kwargs.pop("metadata", {})
        self._metadata = [(key, value) for key, value in metadata.items()]

        _proto_args = kwargs.pop("proto", {})
        check_expected_keys(expected_blocks["proto"], _proto_args)

        self._attempt_reflection = bool(kwargs.pop("attempt_reflection", False))

        if default_host := _connect_args.get("host"):
            self.default_host = default_host
            if port := _connect_args.get("port"):
                self.default_host += ":{}".format(port)

        self.timeout = int(_connect_args.get("timeout", 5))
        self.tls = bool(_connect_args.get("tls", False))

        self.channels = {}
        self.sym_db = _symbol_database.Default()

        if proto_source := _proto_args.get("source"):
            # TODO: Use a temp dir instead?
            _generate_proto_import(proto_source, "proto")

        if proto_module := _proto_args.get("module"):
            if proto_module.endswith(".py"):
                raise exceptions.GRPCServiceException(
                    f"grpc module definitions should not end with .py, but got {proto_module}"
                )

            try:
                _import_grpc_module(proto_module)
            except ImportError as e:
                raise exceptions.GRPCServiceException(
                    "error importing gRPC modules"
                ) from e

    def _register_file_descriptor(
        self,
        service_proto: grpc_reflection.v1alpha.reflection_pb2.FileDescriptorResponse,
    ):
        for file_descriptor_proto in service_proto.file_descriptor_proto:
            proto = descriptor_pb2.FileDescriptorProto()
            proto.ParseFromString(file_descriptor_proto)
            logger.critical("ksdo")
            self.sym_db.pool.Add(proto)

    def _get_reflection_info(
        self, channel, service_name: Optional[str] = None, file_by_filename=None
    ):
        logger.debug(
            "Getting GRPC protobuf for service %s from reflection", service_name
        )
        ref_request = reflection_pb2.ServerReflectionRequest(
            file_containing_symbol=service_name, file_by_filename=file_by_filename
        )
        reflection_stub = reflection_pb2_grpc.ServerReflectionStub(channel)
        ref_response = reflection_stub.ServerReflectionInfo(
            iter([ref_request]), metadata=self._metadata
        )
        for response in ref_response:
            self._register_file_descriptor(response.file_descriptor_response)

    def _get_grpc_service(self, channel, service: str, method: str):
        full_service_name = "{}.{}".format(service, method)
        try:
            grpc_service = self.sym_db.pool.FindMethodByName(full_service_name)
            input_type = message_factory.GetMessageClass(grpc_service.input_type)  # type: ignore
            output_type = message_factory.GetMessageClass(grpc_service.output_type)  # type: ignore
        except KeyError:
            return None, None

        service_url = "/{}/{}".format(service, method)
        grpc_method = channel.unary_unary(
            service_url,
            request_serializer=input_type.SerializeToString,
            response_deserializer=output_type.FromString,
        )

        return grpc_method, input_type

    def _make_call_request(self, host: str, full_service: str):
        full_service = full_service.replace("/", ".")
        service_method = full_service.rsplit(".", 1)
        if len(service_method) != 2:
            raise exceptions.GRPCRequestException("Could not find method name")

        service = service_method[0]
        method = service_method[1]
        logger.debug(
            "Make call for host %s service %s method %s", host, service, method
        )

        if host not in self.channels:
            if self.tls:
                credentials = grpc.ssl_channel_credentials()
                self.channels[host] = grpc.secure_channel(
                    host,
                    credentials,
                    options=[("grpc.max_receive_message_length", 10 * 1024 * 1024)],
                )
            else:
                self.channels[host] = grpc.insecure_channel(
                    host,
                    options=[("grpc.max_receive_message_length", 10 * 1024 * 1024)],
                )

        channel = self.channels[host]

        grpc_method, input_type = self._get_grpc_service(channel, service, method)
        if grpc_method and input_type:
            return grpc_method, input_type

        if not self._attempt_reflection:
            logger.error(
                "could not find service and gRPC reflection disabled, cannot continue"
            )
            raise exceptions.GRPCServiceException(
                "Service {} was not registered for host {}".format(service, host)
            )

        logger.info("service not registered, doing reflection from server")
        try:
            self._get_reflection_info(channel, service_name=service)
        except (
            grpc.RpcError
        ) as rpc_error:  # Since this object is guaranteed to be a grpc.Call, might as well include that in its name.
            code = details = None
            try:
                code = rpc_error.code()
                details = rpc_error.details()
            except AttributeError:
                status = rpc_status.from_call(rpc_error)
                if status is None:
                    logger.warning("Unknown error occurred in RPC call", exc_info=True)
                else:
                    code = status.code
                    details = status.details

            if code and details:
                logger.warning(
                    "Unable get %s service reflection information code %s detail %s",
                    service,
                    code,
                    details,
                    exc_info=True,
                )

            raise exceptions.GRPCRequestException from rpc_error

        return self._get_grpc_service(channel, service, method)

    def __enter__(self):
        logger.debug("Connecting to GRPC")

    def call(
        self,
        service: str,
        host: Optional[str] = None,
        body: Optional[Mapping] = None,
        timeout: Optional[int] = None,
    ):
        if host is None:
            host = self.default_host
        if timeout is None:
            timeout = self.timeout

        grpc_call, grpc_request = self._make_call_request(host, service)
        if grpc_call is None or grpc_request is None:
            raise exceptions.GRPCServiceException(
                "Service {} was not found on host {}".format(service, host)
            )

        request = grpc_request()
        if body is not None:
            try:
                request = json_format.ParseDict(body, request)
            except ParseError as e:
                raise exceptions.GRPCRequestException(
                    "error creating request from json body"
                ) from e

        logger.debug("Send request %s", request)

        return grpc_call.future(request, metadata=self._metadata, timeout=timeout)

    def __exit__(self, *args):
        logger.debug("Disconnecting from GRPC")
