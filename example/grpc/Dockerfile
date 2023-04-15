FROM python:3.9-slim-buster

RUN pip install grpcio==1.51.1 grpcio-reflection==1.51.1 grpcio-status==1.51.1 grpc-interceptor==0.15.1

COPY server/server.py /
COPY server/helloworld_pb2.py /
COPY server/helloworld_pb2_grpc.py /

CMD ["python3", "/server.py"]
