from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tavern._core.pytest.config import TestConfig


class TavernException(Exception):
    """Base exception

    Fields are internal and might change in future without warning

    Attributes:
        is_final: whether this exception came from a 'finally' block
        stage: stage that caused this issue
        test_block_config: config for stage
    """

    stage: Optional[dict]
    test_block_config: Optional["TestConfig"]
    is_final: bool = False


class BadSchemaError(TavernException):
    """Schema mismatch"""


class EvalError(TavernException):
    """Error parsing or running a simpleeval program"""


class TestFailError(TavernException):
    """Test failed somehow"""

    def __init__(self, msg, failures=None) -> None:
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


class GRPCRequestException(TavernException):
    """Error making requests in GRPCRequest()"""


class GRPCServiceException(TavernException):
    """Some kind of error when trying to get the gRPC service"""


class ProtoCompilerException(TavernException):
    """Some kind of error using protoc"""


class MQTTRequestException(TavernException):
    """Error making requests in MQTTRequest()"""


class MQTTTopicException(TavernException):
    """Internal (?) error with subscriptions"""


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


class MisplacedExtBlockException(TavernException):
    """Tried to use the '$ext' block in a place it is no longer valid to use it"""

    def __init__(self, block) -> None:
        super().__init__(
            f"$ext function found in block {block} - this has been moved to verify_response_with block - see documentation"
        )


class InvalidRetryException(TavernException):
    """Invalid spec for max_retries"""


class RegexAccessError(TavernException):
    """Error accessing a key via regex"""


class DuplicateStrictError(TavernException):
    """Tried to set stage strictness for multiple responses"""


class ConcurrentError(TavernException):
    """Error while processing concurrent future"""


class UnexpectedExceptionError(TavernException):
    """We expected a certain kind of exception in check_exception_raised but it was something
    else"""
