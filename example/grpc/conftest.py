import tempfile

import pytest


@pytest.fixture()
def make_temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d
