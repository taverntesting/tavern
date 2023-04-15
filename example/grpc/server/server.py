from concurrent import futures
import logging
import threading

import grpc
from grpc_reflection.v1alpha import reflection

import helloworld_pb2
import helloworld_pb2_grpc


class Greeter(helloworld_pb2_grpc.GreeterServicer):

    def SayHello(self, request, context):
        return helloworld_pb2.HelloReply(message='Hello, %s!' % request.name)


def serve():
    for reflect in [True, False]:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)

        if reflect:
            service_names = (
                helloworld_pb2.DESCRIPTOR.services_by_name['Greeter'].full_name,
                reflection.SERVICE_NAME,
            )
            reflection.enable_server_reflection(service_names, server)
            port = 50052
        else:
            port = 50051

        server.add_insecure_port(f'[::]:{port:d}')
        logging.info("Starting...")
        server.start()

    event = threading.Event()
    event.wait()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
