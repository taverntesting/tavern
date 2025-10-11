FROM python:3.12-slim-trixie AS base

RUN pip install grpcio-tools==1.59.0 grpcio==1.59.0 grpcio-reflection==1.59.0 grpcio-status==1.59.0 grpc-interceptor==0.15.3


FROM base AS protos

RUN apt-get update  && apt-get install protobuf-compiler --yes --no-install-recommends && apt-get clean

COPY *.proto .

RUN python3 -m grpc_tools.protoc --proto_path=$(pwd) --pyi_out=$(pwd) --python_out=$(pwd) --grpc_python_out=$(pwd) *.proto



FROM base

COPY --from=protos /*.py /

COPY server/server.py /

CMD ["python3", "/server.py"]
