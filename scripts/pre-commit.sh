#!/usr/bin/env bash

bazel run //:gazelle_python_manifest.update
bazel run //:gazelle
#bazel run --run_under "cd $PWD && " @bazel_buildtools//buildozer \
go run github.com/bazelbuild/buildtools/buildozer@latest \
  'substitute deps "@tavern_pip//([^/]+)" requirement(${1})' //...:*
