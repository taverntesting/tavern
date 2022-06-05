import os
import sys

import pytest
# gazelle:ignore rules_python.python.runfiles
from rules_python.python.runfiles import runfiles
import stevedore

import tavern
import tavern._plugins.mqtt.tavernhook as mqtt_plugin
from tavern._plugins.rest.tavernhook import TavernRestPlugin as rest_plugin
from tavern.testutils import pytesthook

if __name__ == '__main__':
    def extension(name, point):
        return stevedore.extension.Extension(name, point, point, point)


    tavern.plugins.load_plugins.plugins = [
        extension(
            "requests",
            rest_plugin,
        ),
        extension(
            "paho-mqtt",
            mqtt_plugin,
        ),
    ]

    r = runfiles.Create()

    test_file_location_ = os.environ["TAVERN_TEST_FILE_LOCATION"]
    os_path_dirname = os.path.dirname(test_file_location_)

    sys.path.append(os_path_dirname)

    raise SystemExit(pytest.main([test_file_location_] + sys.argv[2:], plugins=[pytesthook]))
