import os


def bazel_path(inpath):
    try:
        # gazelle:ignore rules_python.python.runfiles
        from rules_python.python.runfiles import runfiles
    except ImportError:
        return inpath
    else:
        yaml_path = os.path.dirname(os.getenv("TEST_BINARY"))
        b = os.path.join(yaml_path, inpath)
        return b
