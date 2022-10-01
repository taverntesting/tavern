# Bazel development

## Setup

Install [Bazelisk](https://github.com/bazelbuild/bazelisk), _NOT_ Bazel

## Running unit tests

    bazel test //tests/unit/...

## Running integration tests and unit tests

    bazel test //...

## Adding/changing a dependency

1. Add any dependencies into requirements.in
2. Check dependencies can be resolved

       bazel test //:requirements_test

3. Update requirements.txt

       bazel run //:requirements.update

4. Run tests as before

## Running after changing any imports etc.

1. Run gazelle and fix up dependencies

       bazel run //:gazelle
       bazel run --run_under "cd $PWD && " @bazel_buildtools//buildozer 'substitute deps @tavern_pip//pypi__([^/]+) @tavern_pip_${1}//:pkg' //...:*

See also [the existing script to do this](/scripts/pre-commit.sh)

## Loading docker images

    docker load -i $(bazel run --run_under "ls " //tests:test_image_bundle.tar)
