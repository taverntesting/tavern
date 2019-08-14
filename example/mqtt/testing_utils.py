def message_says_hello(response):
    """Make sure that the response was friendly
    """
    assert response.payload == "hello world"
