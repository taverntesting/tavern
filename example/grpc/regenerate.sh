#!/usr/bin/env bash

python3 -m grpc_tools.protoc --proto_path=$(pwd) --pyi_out=$(pwd) --python_out=$(pwd) --grpc_python_out=$(pwd) helloworld_v1_precompiled.proto
ruff format *pb2*py
