def message_says_hello(msg):
    """Make sure that the response was friendly"""
    assert msg.payload.get("message") == "hello world"
