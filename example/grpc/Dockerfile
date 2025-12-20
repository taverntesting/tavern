FROM python:3.11-slim-trixie AS base

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync


FROM base AS protos

RUN apt-get update  && apt-get install protobuf-compiler --yes --no-install-recommends && apt-get clean

COPY *.proto .

RUN uv run -m grpc_tools.protoc --proto_path=$(pwd) --pyi_out=$(pwd) --python_out=$(pwd) --grpc_python_out=$(pwd) *.proto


FROM base

COPY --from=protos /app/*.py /app/

ENV PYTHONPATH=.
CMD ["uv", "run", "/app/tavern_grpc_example/server.py"]
