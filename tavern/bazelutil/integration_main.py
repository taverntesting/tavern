import json
import os
import time

import docker
import pytest
import sys
# gazelle:ignore rules_python.python.runfiles
from rules_python.python.runfiles import runfiles

from tavern.bazelutil.bazel import enable_default_tavern_extensions
from tavern.testutils import pytesthook

if __name__ == '__main__':
    enable_default_tavern_extensions()

    runfiles = runfiles.Create()

    test_file_location_ = os.environ["TAVERN_TEST_FILE_LOCATION"]
    os_path_dirname = os.path.dirname(test_file_location_)

    sys.path.append(os_path_dirname)

    client = docker.from_env()
    with open(os.environ["TAVERN_DOCKER_IMAGES"], "r") as image_file:
        images = json.load(image_file)

    container = client.containers.run(images[0], detach=True, ports={
        5000: os.environ["TAVERN_DOCKER_PORT"]})
    time.sleep(3)

    try:
        raise SystemExit(
            pytest.main([test_file_location_] + sys.argv[2:],
                        plugins=[pytesthook]))
    finally:
        container.stop(timeout=3)
