def message_says_hello(msg):
    """Make sure that the response was friendly"""
    assert msg.msg.payload.get("message") == "hello world"


def return_hello(_=None):
    return {"hello": "there"}
