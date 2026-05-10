import time

from requests.auth import AuthBase, HTTPDigestAuth


class PizzaAuth(AuthBase):
    """Attaches HTTP Pizza Authentication to the given Request object."""

    def __init__(self, username):
        self.username = username

    def __call__(self, r):
        r.headers["X-Pizza"] = self.username
        return r


def return_hello():
    return {"hello": "there"}


def return_goodbye_string():
    return "goodbye"


def return_list_vals():
    return [{"a_value": "b_value"}, 2]


def gen_echo_url(host):
    return f"{host}/echo"


def get_digest_auth():
    return HTTPDigestAuth("fakeuser", "fakepass")


def get_pizza_auth():
    return PizzaAuth("pizza_user")


def time_request(_):
    time.time()
    yield
    time.time()


def print_response(_, extra_print="affa"):
    (_, r) = yield
