"""Configuration for GraphQL integration tests"""

import pytest
import threading
import time
from flask import Flask

from .test_server import app


@pytest.fixture(scope="session")
def graphql_server_url():
    """Return the URL of the GraphQL test server"""
    return "http://localhost:8001"


@pytest.fixture(scope="session", autouse=True)
def graphql_test_server():
    """Start a GraphQL test server for integration tests"""
    import threading
    import time
    import sys

    # Run server in a separate thread
    server_thread = threading.Thread(
        target=lambda: app.run(host="localhost", port=8001, debug=False, use_reloader=False)
    )
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to start
    time.sleep(1)

    # Verify server is running
    import requests
    max_retries = 5
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8001/health", timeout=1)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            if i == max_retries - 1:
                raise Exception("Failed to start GraphQL test server")
            time.sleep(0.5)

    yield

    # Cleanup is handled automatically when thread ends