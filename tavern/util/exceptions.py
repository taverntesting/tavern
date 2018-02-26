class TavernException(Exception):
    pass


class BadSchemaError(TavernException):
    """Schema mismatch
    """
    pass


class TestFailError(TavernException):
    """Test failed somehow
    """
    pass


class UnexpectedKeysError(TavernException):
    """Unexpected keys used in request specification
    """
    pass


class DuplicateKeysError(TavernException):
    """Duplicate key in request specification
    """
    pass


class MissingKeysError(TavernException):
    """Missing key in request specification
    """
    pass


class MissingFormatError(TavernException):
    """Tried to use a variable in a format string but it was not in the
    available variables
    """
    pass


class MissingSettingsError(TavernException):
    """Wanted to send an MQTT message but no settings were given
    """


class MQTTError(TavernException):
    """Some kind of error returned from paho library
    """


class MissingCookieError(TavernException):
    """Tried to use a cookie in a request that was not present in the session
    cookie jar
    """
    pass


class RestRequestException(TavernException):
    """Error making requests in RestRequest()
    """


class MQTTRequestException(TavernException):
    """Error making requests in MQTTRequest()
    """


class MQTTTLSError(TavernException):
    """Error with TLS arguments to MQTT client"""
