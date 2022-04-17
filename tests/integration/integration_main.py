import sys

import pytest
from rules_python.python.runfiles import runfiles

from tavern.testutils import pytesthook

if __name__ == '__main__':
    r = runfiles.Create()
    test_location = r.Rlocation("tavern/tests/integration/" + sys.argv[1])

    raise SystemExit(pytest.main([test_location] + sys.argv[2:], plugins=[pytesthook]))
