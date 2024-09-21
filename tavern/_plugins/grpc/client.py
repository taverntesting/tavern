import dataclasses
import logging
import warnings
from collections.abc import Mapping
from typing import Any, Optional

import grpc
import grpc_reflection
import proto.message
from google._upb._message import DescriptorPool
from google.protobuf import (
    descriptor_pb2,
    json_format,
    message_factory,
    symbol_database,
)
from google.protobuf.json_format import ParseError
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
from grpc_status import rpc_status

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys
from tavern._plugins.grpc.protos import _generate_proto_import, _import_grpc_module

logger: logging.Logger = logging.getLogger(__name__)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    warnings.warn("deprecated", DeprecationWarning)  # noqa: B028

_ProtoMessageType = type[proto.message.Message]


@dataclasses.dataclass
class _ChannelVals:
    channel: grpc.UnaryUnaryMultiCallable
    input_type: _ProtoMessageType
    output_type: _ProtoMessageType


class GRPCClient:
    def __init__(self, **kwargs) -> None:
        logger.debug("Initialising GRPC client with %s", kwargs)
        expected_blocks = {
            "connect": {"host", "port", "options", "timeout", "secure"},
            "proto": {"source", "module"},
            "metadata": {},
            "attempt_reflection": {},
        }
        # check main block first
        check_expected_keys(expected_blocks.keys(), kwargs)

        _connect_args = kwargs.pop("connect", {})
        check_expected_keys(expected_blocks["connect"], _connect_args)

        metadata = kwargs.pop("metadata", {})
        self._metadata = list(metadata.items())

        _proto_args = kwargs.pop("proto", {})
        check_expected_keys(expected_blocks["proto"], _proto_args)

        self._attempt_reflection = bool(kwargs.pop("attempt_reflection", False))

        if default_host := _connect_args.get("host"):
            self.default_host = default_host
            if port := _connect_args.get("port"):
                self.default_host += f":{port}"

        self.timeout = int(_connect_args.get("timeout", 5))
        self.secure = bool(_connect_args.get("secure", False))

        self._options: list[tuple[str, Any]] = []
        for key, value in _connect_args.pop("options", {}).items():
            if not key.startswith("grpc."):
                raise exceptions.GRPCServiceException(
                    f"invalid grpc option '{key}' - must be in the form 'grpc.option_name'"
                )
            self._options.append((key, value))

        self.channels: dict[str, grpc.Channel] = {}
        # Using the default symbol database is a bit undesirable because it means that things being imported from
        # previous tests will affect later ones which can mask bugs. But there isn't a nice way to have a
        # self-contained symbol database, because then you need to transitively import all dependencies of protos and
        # add them to the database.
        self.sym_db = symbol_database.Default()

        if proto_source := _proto_args.get("source"):
            _generate_proto_import(proto_source)

        if proto_module := _proto_args.get("module"):
            try:
                _import_grpc_module(proto_module)
            except (ImportError, ModuleNotFoundError) as e:
                logger.exception(f"could not import {proto_module}")
                raise exceptions.GRPCServiceException(
                    "error importing gRPC modules"
                ) from e

    def _register_file_descriptor(
        self,
        service_proto: grpc_reflection.v1alpha.reflection_pb2.FileDescriptorResponse,
    ) -> None:
        for file_descriptor_proto in service_proto.file_descriptor_proto:
            descriptor = descriptor_pb2.FileDescriptorProto()
            descriptor.ParseFromString(file_descriptor_proto)
            self.sym_db.pool.Add(descriptor)

    def _get_reflection_info(
        self, channel, service_name: Optional[str] = None, file_by_filename=None
    ) -> None:
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

    def _get_grpc_service(
        self, channel: grpc.Channel, service: str, method: str
    ) -> Optional[_ChannelVals]:
        full_service_name = f"{service}/{method}"
        try:
            input_type, output_type = self.get_method_types(full_service_name)
        except KeyError as e:
            logger.debug(f"could not find types: {e}")
            return None

        logger.info(f"reflected info for {service}: {full_service_name}")

        grpc_method = channel.unary_unary(
            "/" + full_service_name,
            request_serializer=input_type.SerializeToString,
            response_deserializer=output_type.FromString,
        )

        return _ChannelVals(grpc_method, input_type, output_type)

    def get_method_types(
        self, full_method_name: str
    ) -> tuple[_ProtoMessageType, _ProtoMessageType]:
        """Uses the builtin symbol pool to try and find the input and output types for the given method

        Args:
            full_method_name: full RPC name in the form 'pkg.ServiceName/Method'

        Returns:
            input and output types (class objects) for the RPC

        Raises:
            KeyError: If the types are not registered. Should ideally never happen?
        """
        logger.debug(f"looking up types for {full_method_name}")

        service, method = full_method_name.split("/")

        pool: DescriptorPool = self.sym_db.pool
        grpc_service = pool.FindServiceByName(service)
        method = grpc_service.FindMethodByName(method)
        input_type = message_factory.GetMessageClass(method.input_type)  # type: ignore
        output_type = message_factory.GetMessageClass(method.output_type)  # type: ignore

        return input_type, output_type

    def _make_call_request(
        self, host: str, full_service: str
    ) -> Optional[_ChannelVals]:
        full_service = full_service.replace("/", ".")
        service_method = full_service.rsplit(".", 1)
        if len(service_method) != 2:
            raise exceptions.GRPCRequestException(
                f"Invalid service/method name {full_service}"
            )

        service = service_method[0]
        method = service_method[1]
        logger.debug(
            "Make call for host %s service %s method %s", host, service, method
        )

        if host not in self.channels:
            if self.secure:
                credentials = grpc.ssl_channel_credentials()
                self.channels[host] = grpc.secure_channel(
                    host,
                    credentials,
                    options=self._options,
                )
            else:
                self.channels[host] = grpc.insecure_channel(
                    host,
                    options=self._options,
                )

        channel = self.channels[host]

        if channel_vals := self._get_grpc_service(channel, service, method):
            return channel_vals

        if not self._attempt_reflection:
            logger.error(
                "could not find service and gRPC reflection disabled, cannot continue"
            )
            raise exceptions.GRPCServiceException(
                f"Service {service} was not registered for host {host}"
            )

        logger.info("service not registered, doing reflection from server")
        try:
            self._get_reflection_info(channel, service_name=service)
        except grpc.RpcError as rpc_error:
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

    def __enter__(self) -> "GRPCClient":
        logger.debug("Connecting to GRPC")
        return self

    def call(
        self,
        service: str,
        host: Optional[str] = None,
        body: Optional[Mapping] = None,
        timeout: Optional[int] = None,
    ) -> grpc.Future:
        """Makes the request and returns a future with the response."""
        if host is None:
            if getattr(self, "default_host", None) is None:
                raise exceptions.GRPCRequestException(
                    "no host specified in request and no default host in settings"
                )

            host = self.default_host

        if timeout is None:
            timeout = self.timeout

        channel_vals = self._make_call_request(host, service)
        if channel_vals is None:
            raise exceptions.GRPCServiceException(
                f"Service {service} was not found on host {host}"
            )

        request = channel_vals.input_type()
        if body is not None:
            try:
                request = json_format.ParseDict(body, request)
            except ParseError as e:
                raise exceptions.GRPCRequestException(
                    "error creating request from json body"
                ) from e

        logger.debug("Sending request %s", request)

        return channel_vals.channel.future(
            request, metadata=self._metadata, timeout=timeout
        )

    def __exit__(self, *args) -> None:
        logger.debug("Disconnecting from GRPC")
        for v in self.channels.values():
            v.close()
        self.channels = {}
