import stevedore


def enable_default_tavern_extensions():
    # pylint: disable=protected-access
    def extension(name, point):
        return stevedore.extension.Extension(name, point, point, point)

    import tavern
    from tavern._plugins.mqtt import tavernhook as mqtt_plugin
    from tavern._plugins.rest.tavernhook import TavernRestPlugin as rest_plugin

    tavern._core.plugins.load_plugins.plugins = [
        extension(
            "requests",
            rest_plugin,
        ),
        extension(
            "paho-mqtt",
            mqtt_plugin,
        ),
    ]
