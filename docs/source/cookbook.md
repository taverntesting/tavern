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

## Use with Locust

**NOTE: This is just an example, do not consider this part of Tavern
or to be supported in any way.**

[Locust](https://locust.io/) is a simple Python based load testing tool
which can be used to flood your API with requests to see how it handles
under load. This is not a good map for Tavern because every time you run 
even a single test you incur the cost of starting Pytest, collecting
files, etc., but if you do want to be able to see how your existing API
can handle a few tens of requests per second before using tools more
suited to the job (such as [Gatling](https://github.com/gatling/gatling)),
integrating your current Tavern tests with Locust is a good start.

You can define your own client which just runs Tavern tests like so:

```python
import time
from locust import Locust, events
from tavern.core import run


class TavernClient(object):
    def __init__(self, *args, **kwargs):
        super(TavernClient, self).__init__(*args, **kwargs)

    def run_tavern_tests(
        self,
        names_contain=None,
        mark_specifier=None,
        filename=None,
        extra_pytest_args=None,
    ):
        if not (names_contain or mark_specifier or filename):
            raise RuntimeError(
                "Must specify one of names_contain, mark_specifier, or filename"
            )

        joined_args = ["--disable-pytest-warnings", "--no-cov", "-qqqqqqqq", "-s"]
        
        if extra_pytest_args:
            joined_args += extra_pytest_args

        name = "tavern"

        if filename:
            joined_args += [filename]
            name += "/f:{}".format(filename)
        if mark_specifier:
            joined_args += ["-m", mark_specifier]
            name += "/m:{}".format(",".join(mark_specifier).replace(" ", ""))
        if names_contain:
            joined_args += ["-k", names_contain]
            name += "/k:{}".format(",".join(names_contain).replace(" ", ""))

        start_time = time.time()
        try:
            run(filename, pytest_args=joined_args)
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request_failure.fire(
                request_type="tavern",
                name=name,
                response_time=total_time,
                exception=e
            )
        else:
            total_time = int((time.time() - start_time) * 1000)
            events.request_success.fire(
                request_type="tavern",
                name=name,
                response_time=total_time,
                response_length=0,
            )


class TavernLocust(Locust):
    def __init__(self, *args, **kwargs):
        super(TavernLocust, self).__init__(*args, **kwargs)
        self.client = TavernClient(self.host)
```

This can be used with your task set like this:

```python
from locust import  TaskSet, task
from my.package.name import TavernLocust


class MyTaskSet(TaskSet):
    @task
    def task1(self):
        self.client.run_tavern_tests(filename="test_server.tavern.yaml", names_contain=["doubles"])

    @task
    def task2(self):
        self.client.run_tavern_tests(filename="test_server.tavern.yaml", names_contain=["error"])

    @task
    def task3(self):
        self.client.run_tavern_tests(filename="test_server.tavern.yaml", names_contain=["series"])


class MyLocust(TavernLocust):
    task_set = MyTaskSet
    min_wait = 5
    max_wait = 15
```
