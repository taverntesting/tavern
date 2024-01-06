FROM python:3.10-slim-buster@sha256:37aa274c2d001f09b14828450d903c55f821c90f225fdfdd80c5180fcca77b3f

RUN pip install grpcio==1.59.0 grpcio-reflection==1.59.0 grpcio-status==1.59.0 grpc-interceptor==0.15.3

COPY server/server.py /
COPY server/helloworld_pb2.py /
COPY server/helloworld_pb2_grpc.py /

CMD ["python3", "/server.py"]
