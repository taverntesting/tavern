#!/usr/bin/env bash

python -m grpc_tools.protoc --proto_path=$(pwd) --pyi_out=$(pwd) --python_out=$(pwd) --grpc_python_out=$(pwd) helloworld.proto
