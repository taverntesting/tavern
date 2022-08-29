# Bazel development

## Setup

Install [Bazelisk](https://github.com/bazelbuild/bazelisk), _NOT_ Bazel

## Running unit tests

Run `bazel test //tests/unit/...`

## Running integration tests

1. Build images with `bazel build //tests:test_image_bundle.tar`
2. Load into docker with `docker load -i $(bazel run --run_under "ls " //tests:test_image_bundle.tar)`

## Adding/changing a dependency

1. Add it into requirements.in
2. Run `bazel test //:requirements_test`
3. Run `bazel run //:requirements.update`
4. Run tests as before
