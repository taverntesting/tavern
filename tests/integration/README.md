# Random integration tests

Though there are full examples for testing MQTT, cookies, etc, this subfolder
contains more 'generic' tests such as testing regex functionality and pattern
matching that don't nicely slot into the examples. Essentially, tests in this
folder will typically consist of one stage (unless multi-stage functionality is
being tested), and will not require logging in.

For the time being, all the random tests are just being put into the same
server.py and will be run with docker.
