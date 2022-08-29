#!/usr/bin/env bash

set -ex

bazel build $(bazel query 'kind("(.*_image|_app_layer)", //...)' )
