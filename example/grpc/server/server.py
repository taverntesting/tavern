import logging
import threading
from collections.abc import Callable
from concurrent import futures
from typing import Any

import grpc
import helloworld_v1_precompiled_pb2 as helloworld_pb2_v1
import helloworld_v1_precompiled_pb2_grpc as helloworld_pb2_grpc_v1
import helloworld_v2_compiled_pb2 as helloworld_pb2_v2
import helloworld_v2_compiled_pb2_grpc as helloworld_pb2_grpc_v2
import helloworld_v3_reflected_pb2 as helloworld_pb2_v3
import helloworld_v3_reflected_pb2_grpc as helloworld_pb2_grpc_v3
from grpc_interceptor import ServerInterceptor
from grpc_interceptor.exceptions import GrpcException
from grpc_reflection.v1alpha import reflection


class GreeterV1(helloworld_pb2_grpc_v1.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2_v1.HelloReply(message=f"Hello, {request.name}!")


class GreeterV2(helloworld_pb2_grpc_v2.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2_v2.HelloReply(message=f"Hello, {request.name}!")


class GreeterV3(helloworld_pb2_grpc_v3.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2_v3.HelloReply(message=f"Hello, {request.name}!")


class LoggingInterceptor(ServerInterceptor):
    def intercept(
        self,
        method: Callable,
        request_or_iterator: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        logging.info(f"got request on {method_name}")

        try:
            return method(request_or_iterator, context)
        except GrpcException as e:
            logging.exception("error processing request")
            context.set_code(e.status_code)
            context.set_details(e.details)
            raise


def serve():
    interceptors = [LoggingInterceptor()]
    executor = futures.ThreadPoolExecutor(max_workers=10)

    # One server which exposes these two
    server = grpc.server(
        executor,
        interceptors=interceptors,
    )
    helloworld_pb2_grpc_v1.add_GreeterServicer_to_server(GreeterV1(), server)
    helloworld_pb2_grpc_v2.add_GreeterServicer_to_server(GreeterV2(), server)

    server.add_insecure_port("0.0.0.0:50051")
    server.start()

    # One server which exposes the V3 API and has reflection turned on
    reflecting_server = grpc.server(
        executor,
        interceptors=interceptors,
    )
    helloworld_pb2_grpc_v3.add_GreeterServicer_to_server(GreeterV3(), reflecting_server)
    service_names = (
        helloworld_pb2_v3.DESCRIPTOR.services_by_name["Greeter"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, reflecting_server)
    reflecting_server.add_insecure_port("0.0.0.0:50052")
    reflecting_server.start()

    logging.info("Starting grpc server")
    event = threading.Event()
    event.wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve()
