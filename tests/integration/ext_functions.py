import dataclasses
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


@dataclasses.dataclass
class _TinctureCounter:
    count: int = 0

    def increment(self):
        self.count += 1

    def reset(self):
        self.count = 0


_counter = _TinctureCounter()


def global_tincture_marker(stage):
    """Tincture used to verify global tinctures are applied (issue #969).

    This is a simple tincture that runs before each stage when configured
    globally. It tracks the number of times it's called to verify it's
    invoked for every stage.
    """
    _counter.increment()


def get_global_tincture_call_count():
    """Return the number of times global_tincture_marker was called."""
    return _counter.count


def reset_global_tincture_call_count():
    """Reset the call count (for test isolation)."""
    _counter.reset()
