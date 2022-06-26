import os

import stevedore


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


def enable_default_tavern_extensions():
    def extension(name, point):
        return stevedore.extension.Extension(name, point, point, point)

    import tavern
    from tavern._plugins.mqtt import tavernhook as mqtt_plugin
    from tavern._plugins.rest.tavernhook import TavernRestPlugin as rest_plugin

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
