class TavernException(Exception):
    """Base exception"""


class BadSchemaError(TavernException):
    """Schema mismatch"""


class TestFailError(TavernException):
    """Test failed somehow"""

    def __init__(self, msg, failures=None):
        super().__init__(msg)
        self.failures = failures or []


class KeyMismatchError(TavernException):
    """Mismatch found while validating keys in response"""


class UnexpectedKeysError(TavernException):
    """Unexpected keys used in request specification"""


class DuplicateKeysError(TavernException):
    """Duplicate key in request specification"""


class MissingKeysError(TavernException):
    """Missing key in request specification"""


class MissingFormatError(TavernException):
    """Tried to use a variable in a format string but it was not in the
    available variables
    """


class MissingSettingsError(TavernException):
    """Wanted to send an MQTT message but no settings were given"""


class MQTTError(TavernException):
    """Some kind of error returned from paho library"""


class MissingCookieError(TavernException):
    """Tried to use a cookie in a request that was not present in the session
    cookie jar
    """


class RestRequestException(TavernException):
    """Error making requests in RestRequest()"""


class MQTTRequestException(TavernException):
    """Error making requests in MQTTRequest()"""


class MQTTTLSError(TavernException):
    """Error with TLS arguments to MQTT client"""


class PluginLoadError(TavernException):
    """Error loading a plugin"""


class InvalidExtFunctionError(TavernException):
    """Error loading an external function for validation/plugin use"""


class JMESError(TavernException):
    """Error in JMES matching"""


class InvalidStageReferenceError(TavernException):
    """Error loading stage reference"""


class DuplicateStageDefinitionError(TavernException):
    """Stage with the specified ID previously defined"""


class InvalidSettingsError(TavernException):
    """Configuration was passed incorrectly in some fashion"""


class KeySearchNotFoundError(TavernException):
    """Trying to search for a key in the response but was not found"""


class InvalidQueryResultTypeError(TavernException):
    """Searched for a value in data but it was not a 'simple' type"""


class UnexpectedDocumentsError(TavernException):
    """Multiple documents were found in a YAML file when only one was expected"""


class DuplicateCookieError(TavernException):
    """User tried to reuse a cookie from a previous request and override it in the same request"""


class InvalidConfigurationException(TavernException):
    """A configuration value (from the cli or the ini file) was invalid"""


class InvalidFormattedJsonError(TavernException):
    """Tried to use the magic json format tag in an invalid way"""


class InvalidExtBlockException(TavernException):
    """Tried to use the '$ext' block in a place it is no longer valid to use it"""

    def __init__(self, block):
        super().__init__(
            "$ext function found in block {} - this has been moved to verify_response_with block - see documentation".format(
                block
            )
        )


class InvalidRetryException(TavernException):
    """Invalid spec for max_retries"""


class RegexAccessError(TavernException):
    """Error accessing a key via regex"""


class DuplicateStrictError(TavernException):
    """Tried to set stage strictness for multiple responses"""
