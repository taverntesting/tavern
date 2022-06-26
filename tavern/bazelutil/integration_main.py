import os
import sys

import pytest
# gazelle:ignore rules_python.python.runfiles
from rules_python.python.runfiles import runfiles

from tavern.testutils import pytesthook
from tavern.bazelutil.bazel import enable_default_tavern_extensions

if __name__ == '__main__':
    enable_default_tavern_extensions()

    r = runfiles.Create()

    test_file_location_ = os.environ["TAVERN_TEST_FILE_LOCATION"]
    os_path_dirname = os.path.dirname(test_file_location_)

    sys.path.append(os_path_dirname)

    raise SystemExit(pytest.main([test_file_location_] + sys.argv[2:], plugins=[pytesthook]))
