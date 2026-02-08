# Pytest marks with tests

Since 0.11.0, it is possible to 'mark' tests. This uses Pytest behind the
scenes - see the [pytest mark documentation](https://docs.pytest.org/en/latest/example/markers.html)
for details on their implementation and prerequisites for use.

In short, marks can be used to:

- Select a subset of marked tests to run from the command line
- Skip certain tests based on a condition
- Mark tests as temporarily expected to fail, so they can be fixed later

An example of how these can be used:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - slow

stages:
  - name: Get info
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000

---
test_name: Get server info from fast endpoint

marks:
  - fast

stages:
  - name: Get info
    request:
      url: "{host}/get-info"
      method: GET
    response:
      status_code: 200
      json:
        n_items: 2048
        n_queries: 5
```

Both tests get some server information from our endpoint, but one requires a lot
of backend processing so we don't want to run it on every test run. This can be
selected like this:

```shell
$ py.test -m "not slow"
```

Conversely, if we just want to run all tests marked as 'fast', we can do this:

```shell
$ py.test -m "fast"
```

Marks can only be applied to a whole test, not to individual stages (with the
exception of `skip`, see below).

### Formatting marks

Marks can be formatted just like other variables:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - "{specialmarker}"
```

This is mainly for combining with one or more of the special marks as mentioned
below.

**NOTE**: Do _not_ use the `!raw` token or rely on double curly brace formatting
when formatting markers. Due to pytest-xdist, some behaviour with the formatting
of markers is subtly different than other places in Tavern.

### Special marks

There are 4 different 'special' marks from Pytest which behave the same as if
they were used on a Python test.

**NOTE**: If you look in the Tavern integration tests, you may notice a `_xfail`
key being used in some of the tests. This is for INTERNAL USE ONLY and may be
removed in future without warning.

#### skip

To always skip a test, just use the `skip` marker:

```yaml
...

marks:
  - skip
```

Separately from the markers, individual stages can be skipped by inserting the
`skip` keyword into the stage:

```yaml
stages:
  - name: Get info
    skip: True
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000
```

##### Skipping stages with simpleeval expressions

Stages can be skipped by using a `skip` key that contains a [simpleeval](https://pypi.org/project/simpleeval/) expression. 
This allows for more complex conditional logic to determine if a stage should be skipped.

Example:
```yaml
stages:
  - name: Skip based on variable value
    skip: "{v_int} > 50"
    request:
      url: "{host}/fake_list"
      method: GET
    response:
      status_code: 200
```

In this example, the stage will be skipped if `v_int` is greater than 50. Any valid simpleeval expression can be used.

#### skipif

Sometimes you just want to skip some tests, perhaps based on which server you're
using. Taking the above example of the 'slow' server, perhaps it is only slow
when running against the live server at `www.slow-example.com`, but we still want to
run it in our local tests. This can be achieved using `skipif`:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - slow
  - skipif: "'slow-example.com' in '{host}'"

stages:
  - name: Get info
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000
```

`skipif` should be a mapping containing 1 key, a string that will be directly
passed through to `eval()` and should return `True` or `False`. This string will
be formatted first, so tests can be skipped or not based on values in the
configuration. Because this needs to be a valid piece of Python code, formatted
strings must be escaped as in the example above - using `"'slow-example.com' in
{host}"` will raise an error.

#### xfail

If you are expecting a test to fail for some reason, such as if it's temporarily
broken, a test can be marked as `xfail`. Note that this is probably not what you
want to 'negatively' check something like an API deprecation. For example, this
is not recommended:

```yaml
---
test_name: Get user middle name from endpoint on v1 api

stages:
  - name: Get from endpoint
    request:
      url: "{host}/api/v1/users/{user_id}/get-middle-name"
      method: GET
    response:
      status_code: 200
      json:
        middle_name: Jimmy

---
test_name: Get user middle name from endpoint on v2 api fails

marks:
  - xfail

stages:
  - name: Try to get from v2 api
    request:
      url: "{host}/api/v2/users/{user_id}/get-middle-name"
      method: GET
    response:
      status_code: 200
      json:
        middle_name: Jimmy
```

It would be much better to write a test that made sure that the endpoint just
returned a `404` in the v2 api.

#### parametrize

A lot of the time you want to make sure that your API will behave properly for a
number of given inputs. This is where the parametrize mark comes in:

```yaml
---
test_name: Make sure backend can handle arbitrary data

marks:
  - parametrize:
      key: metadata
      vals:
        - 13:00
        - Reading: 27 degrees
        - 手机号格式不正确
        - ""

stages:
  - name: Update metadata
    request:
      url: "{host}/devices/{device_id}/metadata"
      method: POST
      json:
        metadata: "{metadata}"
    response:
      status_code: 200
```

This test will be run 4 times, as 4 separate tests, with `metadata` being
formatted differently for each time. This behaves like the built in Pytest
`parametrize` mark, where the tests will show up in the log with some extra data
appended to show what was being run, eg `Test Name[John]`, `Test Name[John-Smythe John]`, etc.

The `parametrize` mark should be a mapping with `key` being the value that will
be formatted and `vals` being a list of values to be formatted. Note that
formatting of these values happens after checking for a `skipif`, so a `skipif`
mark cannot rely on a parametrized value.

Multiple marks can be used to parametrize multiple values:

```yaml
---
test_name: Test post a new fruit

marks:
  - parametrize:
      key: fruit
      vals:
        - apple
        - orange
        - pear
  - parametrize:
      key: edible
      vals:
        - rotten
        - fresh
        - unripe

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{edible} {fruit}"
    response:
      status_code: 201
```

This will result in 9 tests being run:

- rotten apple
- rotten orange
- rotten pear
- fresh apple
- fresh orange
- etc.

If you need to parametrize multiple keys but don't want there to be a new test
created for every possible combination, pass a list to `key` instead. Each item
in `val` must then also be a list that is _the same length as the `key`
variable_. Using the above example, perhaps we just want to test the server
works correctly with the items "rotten apple", "fresh orange", and "unripe pear"
rather than the 9 combinations listed above. This can be done like this:

```yaml
---
test_name: Test post a new fruit

marks:
  - parametrize:
      key:
        - fruit
        - edible
      vals:
        - [ rotten, apple ]
        - [ fresh, orange ]
        - [ unripe, pear ]
        # NOTE: we can specify a nested list like this as well:
        # -
        #   - unripe
        #   - pear

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{edible} {fruit}"
    response:
      status_code: 201
```

This will result in only those 3 tests being generated.

This can be combined with the 'simpler' style of parametrisation as well - for
example, to run the above test but also to specify whether the fruit was
expensive or cheap:

```yaml
---
test_name: Test post a new fruit and price

marks:
  - parametrize:
      key:
        - fruit
        - edible
      vals:
        - [ rotten, apple ]
        - [ fresh, orange ]
        - [ unripe, pear ]
  - parametrize:
      key: price
      vals:
        - expensive
        - cheap

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{price} {edible} {fruit}"
    response:
      status_code: 201
```

This will result in 6 tests:

- expensive rotten apple
- expensive fresh orange
- expensive unripe pear
- cheap rotten apple
- cheap fresh orange
- cheap unripe pear

Since 1.19.0 you can now also parametrize generic blocks of data instead of only strings. This can
also be mixed and matched with items which _are_ strings. If you do this, remember to use the
[force_format_include](#Including raw JSON data) tag so it doesn't come out as a string:

```yaml
test_name: Test sending a list of list of keys where one is not a string

marks:
  - parametrize:
      key:
        - fruit
        - colours
      vals:
        - [ apple, [ red, green, pink ] ]
        - [ pear, [ yellow, green ] ]

stages:
  - name: Send fruit and colours
    request:
      url: "{host}/newfruit"
      method: POST
      json:
        fruit: "{fruit}"
        colours: !force_format_include "{colours}"

        # This sends:
        # {
        #   "fruit": "apple",
        #   "colours": [
        #     "red",
        #     "green",
        #     "pink"
        #   ]
        # }
```

The type of the 'val' does not need to be the same for each version of the test, and even external
functions can be used to read values. For example this block will create 6 tests which sets the
`value_to_send` key to a string, a list, or a dictionary:

```yaml
---

test_name: Test parametrizing random different data types in the same test

marks:
  - parametrize:
      key: value_to_send
      vals:
        - a
        - [ b, c ]
        - more: stuff
        - yet: [ more, stuff ]
        - $ext:
            function: ext_functions:return_string
        - and: this
          $ext:
            function: ext_functions:return_dict

          # If 'return_dict' returns {"keys: ["a","b","c"]} this results in:
          # {
          #   "and": "this",
          #   "keys": [
          #     "a",
          #     "b",
          #     "c"
          #   ]
          # }
```

As see in the last example, if the `$ext` function returns a dictionary then it will also be merged
with any existing data in the 'val'. In this case, the return value of the function _must_ be a
dictionary or an error will be raised.

```yaml
    # This would raise an error
    #- and: this
    #  $ext:
    #    function: ext_functions:return_string
```

**NOTE**: Due to implementation reasons it is currently impossible to
parametrize the MQTT QoS parameter.

#### usefixtures

Since 0.15.0 there is limited support for Pytest
[fixtures](https://docs.pytest.org/en/latest/fixture.html) in Tavern tests. This
is done by using the `usefixtures` mark. The return (or `yield`ed) values of any
fixtures will be available to use in formatting, using the name of the fixture.

An example of how this can be used in a test:

```python
# conftest.py

import pytest
import logging
import time


@pytest.fixture
def server_password():
    with open("/path/to/password/file", "r") as pfile:
        password = pfile.read().strip()

    return password


@pytest.fixture(name="time_request")
def fix_time_request():
    t0 = time.time()

    yield

    t1 = time.time()

    logging.info("Test took %s seconds", t1 - t0)
```

```yaml
---
test_name: Make sure server can handle a big query

marks:
  - usefixtures:
      - time_request
      - server_password

stages:
  - name: Do big query
    request:
      url: "{host}/users"
      method: GET
      params:
        n_items: 1000
      headers:
        authorization: "Basic {server_password}"
    response:
      status_code: 200
      json:
        ...
```

The above example will load basic auth credentials from a file, which will be
used to authenticate against the server. It will also time how long the test
took and log it.

`usefixtures` expects a list of fixture names which are then loaded by Pytest -
look at their documentation to see how discovery etc. works.

There are some limitations on fixtures:

- Fixtures are per _test_, not per stage. The above example of timing a test
  will include the (small) overhead of doing validation on the responses,
  setting up the requests session, etc. If the test consists of more than one
  stage, it will time how long both stages took.
- Fixtures should be 'function' or 'session' scoped. 'module' scoped fixtures
  will raise an error and 'class' scoped fixtures may not behave as you expect.
- Parametrizing fixtures does not work - this is a limitation in Pytest.

Fixtures which are specified as `autouse` can also be used without explicitly
using `usefixtures` in a test. This is a good way to essentially precompute a
format variable without also having to use an external function or specify a
`usefixtures` block in every test where you need it.

To do this, just pass the `autouse=True` parameter to your fixtures along with
the relevant scope. Using 'session' will evalute the fixture once at the beginning
of your test run and reuse the return value everywhere else it is used:

```python
@pytest.fixture(scope="session", autouse=True)
def a_thing():
    return "abc"
```

```yaml
---
test_name: Test autouse fixture

stages:
  - name: do something with fixture value
    request:
      url: "{host}/echo"
      method: POST
      json:
        value: "{a_thing}"
```

## Using marks with fixtures

Though passing arguments into fixtures is unsupported at the time of writing,
you can use marks to control the behaviour of fixtures.

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
