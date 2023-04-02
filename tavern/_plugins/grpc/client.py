import logging
import os
import pkgutil
import subprocess
import sys
import warnings
from distutils.spawn import find_executable
from importlib import import_module

import grpc
from google.protobuf import descriptor_pb2, json_format
from google.protobuf import symbol_database as _symbol_database
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
from grpc_status import rpc_status

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys

logger = logging.getLogger(__name__)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    warnings.warn("deprecated", DeprecationWarning)


def find_protoc() -> str:
    # Find the Protocol Compiler.
    if "PROTOC" in os.environ and os.path.exists(os.environ["PROTOC"]):
        return os.environ["PROTOC"]

    if protoc := find_executable("protoc"):
        return protoc

    raise exceptions.ProtoCompilerException


protoc = find_protoc()


def _generate_proto_import(source, output):
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
        if child.rsplit(".", 1)[-1] == "proto"
    ]

    protoc_command = [protoc, "-I" + source, "--python_out=" + output]
    protoc_command.extend(protos)

    call = subprocess.run(protoc_command)
    if call.returncode != 0:
        raise exceptions.ProtoCompilerException(call.stderr)


def _import_grpc_module(output):
    output_path = []
    if os.path.exists(output):
        output_path.append(output)
    else:
        mod = __import__(output, fromlist=[""])
        output_path.extend(mod.__path__)

    sys.path.extend(output_path)
    for _, name, _ in pkgutil.iter_modules(output_path):
        import_module("." + name, package=output)


class GRPCClient(object):
    def __init__(self, **kwargs):
        logger.debug("Initialising GRPC client with %s", kwargs)
        expected_blocks = {
            "connect": {"host", "port", "options", "compression", "timeout", "tls"},
            "proto": {"source", "module"},
            "metadata": {},
        }
        # check main block first
        check_expected_keys(expected_blocks.keys(), kwargs)

        _connect_args = kwargs.pop("connect", {})
        check_expected_keys(expected_blocks["connect"], _connect_args)

        metadata = kwargs.pop("metadata", {})
        self._metadata = [(key, value) for key, value in metadata.items()]

        _proto_args = kwargs.pop("proto", {})
        check_expected_keys(expected_blocks["proto"], _proto_args)

        self.default_host = _connect_args["host"]
        if port := _connect_args.get("port"):
            self.default_host += ":{}".format(port)

        self.timeout = int(_connect_args.get("timeout", 5))
        self.tls = bool(_connect_args.get("tls", False))

        logger.critical(self.default_host)

        self.channels = {}
        self.sym_db = _symbol_database.Default()

        proto_module = _proto_args.get("module", "proto")
        if "source" in _proto_args:
            proto_source = _proto_args["source"]
            _generate_proto_import(proto_source, proto_module)

        _import_grpc_module(proto_module)

    def _register_file_descriptor(self, service_proto):
        for i in range(len(service_proto.file_descriptor_proto)):
            file_descriptor_proto = service_proto.file_descriptor_proto[
                len(service_proto.file_descriptor_proto) - i - 1
            ]
            proto = descriptor_pb2.FileDescriptorProto()
            proto.ParseFromString(file_descriptor_proto)
            self.sym_db.pool.Add(proto)

    def _get_reflection_info(self, channel, service_name=None, file_by_filename=None):
        logger.debug("Geting GRPC protobuf for service %s", service_name)
        ref_request = reflection_pb2.ServerReflectionRequest(
            file_containing_symbol=service_name, file_by_filename=file_by_filename
        )
        reflection_stub = reflection_pb2_grpc.ServerReflectionStub(channel)
        ref_response = reflection_stub.ServerReflectionInfo(
            iter([ref_request]), metadata=self._metadata
        )
        for response in ref_response:
            self._register_file_descriptor(response.file_descriptor_response)

    def _get_grpc_service(self, channel, service, method):
        full_service_name = "{}.{}".format(service, method)
        try:
            grpc_service = self.sym_db.pool.FindMethodByName(full_service_name)
            input_type = self.sym_db.GetPrototype(grpc_service.input_type)
            output_type = self.sym_db.GetPrototype(grpc_service.output_type)
        except KeyError:
            return None, None

        service_url = "/{}/{}".format(service, method)
        grpc_method = channel.unary_unary(
            service_url,
            request_serializer=input_type.SerializeToString,
            response_deserializer=output_type.FromString,
        )

        return grpc_method, input_type

    def _make_call_request(self, host, full_service):
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
        if grpc_method is not None and input_type is not None:
            return grpc_method, input_type

        try:
            self._get_reflection_info(channel, service_name=service)
        except (
            grpc.RpcError
        ) as rpc_error:  # Since this object is guaranteed to be a grpc.Call, might as well include that in its name.
            logger.error("Call failure: %s", rpc_error)
            status = rpc_status.from_call(rpc_error)
            if status is None:
                logger.warning("Error occurred %s", rpc_error)
            else:
                logger.warning(
                    "Unable get %s service reflection information code %s detail %s",
                    service,
                    status.code,
                    status.details,
                )
            raise exceptions.GRPCRequestException from rpc_error

        return self._get_grpc_service(channel, service, method)

    def __enter__(self):
        logger.debug("Connecting to GRPC")

    def call(self, service, host=None, body=None, timeout=None):
        if host is None:
            host = self.default_host
        if timeout is None:
            timeout = self.timeout

        grpc_call, grpc_request = self._make_call_request(host, service)
        if grpc_call is None or grpc_request is None:
            raise exceptions.GRPCRequestException(
                "Service {} was not found on host {}".format(service, host)
            )

        request = grpc_request()
        if body is not None:
            request = json_format.ParseDict(body, request)

        logger.debug("Send request %s", request)

        return grpc_call.future(request, metadata=self._metadata, timeout=timeout)

    def __exit__(self, *args):
        logger.debug("Disconnecting from GRPC")
