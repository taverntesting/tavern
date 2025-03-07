# Advanced Cookbook

This page contains some extra reading you might find useful when
writing and running your Tavern tests.

## Pytest plugins

Because Tavern is built upon Pytest, The majority of Pytest plugins can
be used seamlessly to help your testing.

- `pytest-sugar` and `pytest-tldr` can all be used
to make test result reporting more pretty or less pretty.
- `pytest-instafail` shows errors in line while tests are running
- `pytest-html` can be used to provide html reports of test runs
- `pytest-xdist` can be used to run your tests in parallel, speeding up
test runs if you have a large number of tests

## Using with docker

Tavern can be fairly easily used with Docker to run your integration tests. Simply
use this Dockerfile as a base and add any extra requirements you need (such as
any Pytest plugins as mentioned above):

```dockerfile
# tavern.Dockerfile
FROM python:3.10-slim

RUN pip3 install tavern
```

Build with:

```shell
docker build --file tavern.Dockerfile --tag tavern:latest .
```

Or if you need a specific version (hopefully you shouldn't):

```dockerfile
# tavern.Dockerfile
FROM python:3.10-slim

ARG TAVERNVER
RUN pip3 install tavern==$TAVERNVER
```

```shell
export TAVERNVER=0.24.0
docker build --build-arg TAVERNVER=$TAVERNVER --file tavern.Dockerfile --tag tavern:$TAVERNVER .
```

Note that if you do this in a folder with a lot of subfolders (for example, an
npm project) you probably want to create a `.dockerignore` file so that the build
does not take an incredibly long time to start up - see the documentation
[here](https://docs.docker.com/engine/reference/builder/#dockerignore-file)
for information on how to create one.

This can be used by running it on the command line with `docker run`, but
it is often easier to use it in a docker compose file like this:

```yaml
---
version: '3.4'

services:
  tavern:
    build:
      context: .
      dockerfile: tavern.Dockerfile
    env_file:
      # Any extra environment variables for testing
      # This will probably contain things like names of docker containers to run tests against
      - required-env-keys.env
    volumes:
      # The folder that our integration tests are in
      - ./integration_tests:/integration_tests
      # If you have anything in your pytest configuration it will also need mounting
      # here then pointing to with the -c flag to pytest
    command:
      - python
      - -m
      - pytest
      # Point to any global configuration files
      - --tavern-global-cfg
      - /integration_tests/local_urls.yaml
      # And any other flags you want to pass
      - -p
      - no:logging
      # And then point to the folder we mounted above
      - /integration_tests
  
  # Optionally also just run your application in a docker container as well
  application:
    build:
      context: .
      dockerfile: application.Dockerfile
    command:
      ...
```

## Using marks with fixtures

Though passing arguments into fixtures is unsupported at the time of writing,
you can use [Pytest marks](https://docs.pytest.org/en/latest/mark.html)
to control the behaviour of fixtures.

If you have a fixture that loads some information from a file or some
other external data source, but the behaviour needs to change depending
on which test is being run, this can be done by  marking the test and
accessing the test
[Node](https://docs.pytest.org/en/latest/reference.html#node)
in your fixture to change the behaviour:

```yaml
test_name: endpoint 1 test

marks:
  - endpoint_1
  - usefixtures:
       - read_uuid

stages:
    ...

---
test_name: endpoint 2 test

marks:
  - endpoint_2
  - usefixtures:
       - read_uuid

stages:
    ...
```

In the `read_uuid` fixture:

```python
import pytest
import json

@pytest.fixture
def read_uuid(request):  # 'request' is a built in pytest fixture
    marks = request.node.own_markers
    mark_names = [m.name for m in marks]

    with open("stored_uuids.json", "r") as ufile:
        uuids = json.load(ufile)

    if "endpoint_1" in mark_names:
        return uuids["endpoint_1"]
    elif "endpoint_2" in mark_names:
        return uuids["endpoint_2"]
    else:
        pytest.fail("No marker found on test!")
```
