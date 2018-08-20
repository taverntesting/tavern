def get_paho_mqtt_response_information(message):
    """Get parsed MQTT message information

    Args:
        message (paho.mqtt.MQTTMessage): paho message object

    Returns:
        dict: dictionary with useful message information to log
    """
    info = {}

    info["topic"] = message.topic
    info["payload"] = message.payload

    return info
