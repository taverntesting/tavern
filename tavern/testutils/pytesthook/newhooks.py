# pylint: disable=unused-argument


def pytest_tavern_before_every_test_run(test_dict, variables):
    """Called:

    - directly after fixtures are loaded for a test
    - directly before verifying the schema of the file
    - Before formatting is done on values
    - After fixtures have been resolved
    - After global configuration has been loaded
    - After plugins have been loaded

    Modify the test in-place if you want to do something to it.

    Args:
        test_dict (dict): Test to run
        variables (dict): Available variables
    """
