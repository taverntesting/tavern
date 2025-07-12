"""
Conftest.py for Tavern Getting Started Examples
This file demonstrates how to use Pytest fixtures and mark registration with Tavern.
"""

import pytest
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def pytest_configure(config):
    """
    Register custom marks to avoid warnings.
    This is required for Pytest 7.3.0+ compatibility.
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: mark test to run only with --integration"
    )
    config.addinivalue_line(
        "markers", "parametrize: parameterize tests with different data"
    )
    config.addinivalue_line(
        "markers", "skipif: conditionally skip tests"
    )
    config.addinivalue_line(
        "markers", "xfail: expected to fail"
    )
    config.addinivalue_line(
        "markers", "usefixtures: apply fixtures"
    )

def pytest_addoption(parser):
    """
    Add command line options for test selection.
    """
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run tests marked with @pytest.mark.integration",
    )

def pytest_collection_modifyitems(config, items):
    """
    Modify test collection based on command line options.
    """
    if config.getoption("--integration"):
        # Only run tests marked with 'integration'
        integration_items = [item for item in items if "integration" in item.keywords]
        items[:] = integration_items
    else:
        # Skip tests marked with 'integration' unless --integration is passed
        skip_integration = pytest.mark.skip(reason="Need --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)

@pytest.fixture(scope="session")
def setup_test_data():
    """
    Session-scoped fixture that sets up test data.
    This runs once per test session.
    """
    logger.info("Setting up test data for session")

    # You could set up database connections, create test users, etc.
    # For this example, we'll just log that setup is happening
    setup_data = {
        "session_id": f"session_{int(time.time())}",
        "test_users_created": 0,
        "test_posts_created": 0
    }

    logger.info(f"Test session initialized with ID: {setup_data['session_id']}")

    yield setup_data

    # Cleanup after all tests
    logger.info("Cleaning up test data for session")
    logger.info(f"Session {setup_data['session_id']} completed")

@pytest.fixture(scope="function")
def clean_test_environment():
    """
    Function-scoped fixture that cleans up after each test.
    This runs before and after each test function.
    """
    logger.info("Setting up clean test environment")

    # You could reset database state, clear caches, etc.
    # For this example, we'll just log the cleanup
    test_id = f"test_{int(time.time())}"

    yield test_id

    logger.info(f"Cleaning up test environment for {test_id}")

@pytest.fixture(scope="function")
def authenticated_user():
    """
    Function-scoped fixture that provides an authenticated user session.
    This creates a new user and login session for each test.
    """
    logger.info("Creating authenticated user for test")

    # In a real scenario, you might:
    # 1. Create a test user in the database
    # 2. Login to get a session token
    # 3. Return the session data

    user_data = {
        "username": f"test_user_{int(time.time())}",
        "email": f"test_{int(time.time())}@example.com",
        "session_id": f"session_{int(time.time())}"
    }

    logger.info(f"Created authenticated user: {user_data['username']}")

    yield user_data

    logger.info(f"Cleaning up authenticated user: {user_data['username']}")

@pytest.fixture(scope="function")
def test_post_data():
    """
    Function-scoped fixture that provides test post data.
    """
    return {
        "title": f"Test Post {int(time.time())}",
        "content": f"This is test content created at {time.time()}"
    }

# Example of how to use external functions with Tavern
def generate_test_user():
    """
    External function that can be called from Tavern YAML files.
    Returns a dictionary with test user data.
    """
    return {
        "username": f"generated_user_{int(time.time())}",
        "email": f"generated_{int(time.time())}@example.com"
    }

def validate_response_time(response, max_time=5.0):
    """
    External function that validates response time.
    Can be used in Tavern YAML files with verify_response_with.
    """
    # In a real scenario, you might check response.elapsed.total_seconds()
    # For this example, we'll just return True
    return True

def create_bearer_token(username="testuser"):
    """
    External function that creates a bearer token for authentication.
    Can be used in Tavern YAML files with $ext.
    """
    return f"Bearer {username}_token_{int(time.time())}"
