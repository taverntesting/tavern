FROM python:3.5-slim-jessie

RUN pip install grpcio grpcio-tools grpcio-reflection

COPY server.py /
COPY helloworld_pb2.py /
COPY helloworld_pb2_grpc.py /

CMD ["python3", "/server.py"]
