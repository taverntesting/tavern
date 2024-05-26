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
