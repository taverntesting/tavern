import os.path


def bazel_path(inpath):
    try:
        # gazelle:ignore rules_python.python.runfiles
        from rules_python.python.runfiles import runfiles  # noqa
    except ImportError:
        return inpath
    else:
        r = runfiles.Create()

        # TEST_BINARY is exported by bazel and actually points to the tavern YAML file
        yaml_path = os.path.dirname(os.getenv("TEST_BINARY"))
        return r.Rlocation(os.path.join("tavern", yaml_path, inpath))
