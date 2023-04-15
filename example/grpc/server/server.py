from concurrent import futures
import logging
import threading
from typing import Callable, Any

import grpc
from grpc_interceptor import ServerInterceptor
from grpc_interceptor.exceptions import GrpcException
from grpc_reflection.v1alpha import reflection

import helloworld_pb2
import helloworld_pb2_grpc


class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2.HelloReply(message="Hello, %s!" % request.name)


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
            logging.exception(f"error processing request")
            context.set_code(e.status_code)
            context.set_details(e.details)
            raise


def serve():
    executor = futures.ThreadPoolExecutor(max_workers=10)

    for reflect in [True, False]:
        server = grpc.server(
            executor,
            interceptors=[LoggingInterceptor()],
        )
        helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)

        if reflect:
            service_names = (
                helloworld_pb2.DESCRIPTOR.services_by_name["Greeter"].full_name,
                reflection.SERVICE_NAME,
            )
            reflection.enable_server_reflection(service_names, server)
            port = 50052
        else:
            port = 50051

        server.add_insecure_port(f"[::]:{port:d}")
        logging.info("Starting...")
        server.start()

    event = threading.Event()
    event.wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve()
