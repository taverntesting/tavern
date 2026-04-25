import time


def return_hello():
    return {"hello": "there"}


def return_goodbye_string():
    return "goodbye"


def return_list_vals():
    return [{"a_value": "b_value"}, 2]


def gen_echo_url(host):
    return f"{host}/echo"


def time_request(_):
    time.time()
    yield
    time.time()


def print_response(_, extra_print="affa"):
    (_, r) = yield


def global_tincture_marker(stage):
    """Tincture used to verify global tinctures are applied (issue #969).

    This is a simple tincture that runs before each stage when configured
    globally. It doesn't do anything special - its presence in the global
    config is enough to verify the feature works.
    """
    # Just log that we were called - the test verifies this doesn't error
    pass
