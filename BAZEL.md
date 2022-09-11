# Bazel development

## Setup

Install [Bazelisk](https://github.com/bazelbuild/bazelisk), _NOT_ Bazel

## Running unit tests

Run `bazel test //tests/unit/...`

## Running integration tests

1. Build images with `bazel build //tests:test_image_bundle.tar`
2. Load into docker with `docker load -i $(bazel run --run_under "ls " //tests:test_image_bundle.tar)`

## Adding/changing a dependency

1. Add any dependencies into requirements.in
2. Check dependencies can be resolved
 
        bazel test //:requirements_test
 
3. Update requirements.txt

        bazel run //:requirements.update

4. Run tests as before

## Running after changing any imports etc.

1.  Run gazelle and fix up dependencies

        bazel run //:gazelle
        bazel run --run_under "cd $PWD && " @bazel_buildtools//buildozer 'substitute deps @tavern_pip//pypi__([^/]+) @tavern_pip_${1}//:pkg' //...:*

## Notes

Checking manifests are up-to-date

    bazel test //:gazelle_python_manifest.test
