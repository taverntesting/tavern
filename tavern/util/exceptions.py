class TavernException(Exception):
    """Base exception
    """


class BadSchemaError(TavernException):
    """Schema mismatch
    """


class TestFailError(TavernException):
    """Test failed somehow
    """

    def __init__(self, msg, failures=None):
        super(TestFailError, self).__init__(msg)
        self.failures = failures or []


class KeyMismatchError(TavernException):
    """Mismatch found while validating keys in response
    """


class UnexpectedKeysError(TavernException):
    """Unexpected keys used in request specification
    """


class DuplicateKeysError(TavernException):
    """Duplicate key in request specification
    """


class MissingKeysError(TavernException):
    """Missing key in request specification
    """


class MissingFormatError(TavernException):
    """Tried to use a variable in a format string but it was not in the
    available variables
    """


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


class RestRequestException(TavernException):
    """Error making requests in RestRequest()
    """


class MQTTRequestException(TavernException):
    """Error making requests in MQTTRequest()
    """


class MQTTTLSError(TavernException):
    """Error with TLS arguments to MQTT client"""


class PluginLoadError(TavernException):
    """Error loading a plugin"""


class InvalidExtFunctionError(TavernException):
    """Error loading an external function for validation/plugin use"""


class JMESError(TavernException):
    """Error in JMES matching"""
