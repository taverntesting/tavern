import os.path
import shutil
import tempfile

import pytest


@pytest.fixture()
def make_temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(autouse=True, scope="session")
def single_compiled_proto_for_test():
    with tempfile.TemporaryDirectory() as d:
        proto_filename = "helloworld_v2_compiled.proto"
        dst = os.path.join(d, proto_filename)
        shutil.copy(proto_filename, dst)
        yield dst
