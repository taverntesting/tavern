# Running tavern tests

Say we have a simple server that takes a number and returns the double

(contents of server.py)

And we have the tavern tests

(contents of test_server.tavern.yaml)

Tests can be run in 3 different ways

All of these require tavern to be installed

## Via python

Directly calling the library with the filename:

```python
from tavern.core import run

success = run("test_server.tavern.yaml", {})

if not success:
    print("Error running tests")
```

## Via command line

Use tavern-ci tool to run tests:

```shell
$ tavern-ci test_server.tavern.yaml
$ echo $?
0
```

## Via pytest

Just run pytest and point it towards the integration test folder (or add it to
setup.cfg/tox.ini/etc). It will automatically find the tests via pytests
collection mechanism:

```shell
$ py.test
============================= test session starts ==============================
platform linux -- Python 3.5.2, pytest-3.2.0, py-1.4.34, pluggy-0.4.0
rootdir: /home/developer/project/tests, inifile: setup.cfg
plugins: tavern-0.0.1
collected 4 items 

test_server.tavern.yaml ..

===================== 2 passed, 2 skipped in 0.07 seconds ======================
```
