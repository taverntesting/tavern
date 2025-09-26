[![pypi](https://img.shields.io/pypi/v/tavern.svg)](https://pypi.org/project/tavern/)
[![docs](https://readthedocs.org/projects/pip/badge/?version=latest&style=flat)](https://tavern.readthedocs.io/en/latest/)
![workflow](https://github.com/taverntesting/tavern/actions/workflows/main.yml/badge.svg?branch=master)

# Easier API testing

Tavern is a pytest plugin, command-line tool and Python library for
automated testing of APIs, with a simple, concise and flexible
YAML-based syntax. It's very simple to get started, and highly
customisable for complex tests. Tavern supports testing RESTful APIs as
well as MQTT based APIs.

The best way to use Tavern is with
[pytest](https://docs.pytest.org/en/latest/). Tavern comes with a
pytest plugin so that literally all you have to do is install pytest and
Tavern, write your tests in `.tavern.yaml` files and run pytest. This
means you get access to all of the pytest ecosystem and allows you to do
all sorts of things like regularly run your tests against a test server
and report failures or generate HTML reports.

You can also integrate Tavern into your own test framework or continuous
integration setup using the Python library, or use the command line
tool, `tavern-ci` with bash scripts and cron jobs.

To learn more, check out the [examples](https://taverntesting.github.io/examples) or the complete
[documentation](https://taverntesting.github.io/documentation). If you're interested in contributing
to the project take a look at the [GitHub
repo](https://github.com/taverntesting/tavern).

## Quickstart

First up run `pip install tavern`.

Then, let's create a basic test, `test_minimal.tavern.yaml`:

```yaml
---
# Every test file has one or more tests...
test_name: Get some fake data from the JSON placeholder API

# ...and each test has one or more stages (e.g. an HTTP request)
stages:
  - name: Make sure we have the right ID

    # Define the request to be made...
    request:
      url: https://jsonplaceholder.typicode.com/posts/1
      method: GET

    # ...and the expected response code and body
    response:
      status_code: 200
      json:
        id: 1
        userId: 1
        title: "sunt aut facere repellat provident occaecati excepturi optio reprehenderit"
        body: "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
```

This file can have any name, but if you intend to use Pytest with
Tavern, it will only pick up files called `test_*.tavern.yaml`.

This can then be run like so:

```bash
$ pip install tavern[pytest]
$ py.test test_minimal.tavern.yaml  -v
=================================== test session starts ===================================
platform linux -- Python 3.5.2, pytest-3.4.2, py-1.5.2, pluggy-0.6.0 -- /home/taverntester/.virtualenvs/tavernexample/bin/python3
cachedir: .pytest_cache
rootdir: /home/taverntester/myproject, inifile:
plugins: tavern-0.7.2
collected 1 item

test_minimal.tavern.yaml::Get some fake data from the JSON placeholder API PASSED   [100%]

================================ 1 passed in 0.14 seconds =================================
```

It is strongly advised that you use Tavern with Pytest - not only does
it have a lot of utility to control discovery and execution of tests,
there are a huge amount of plugins to improve your development
experience. If you absolutely can't use Pytest for some reason, use the
`tavern-ci` command line interface:

```bash
$ pip install tavern
$ tavern-ci --stdout test_minimal.tavern.yaml
2017-11-08 16:17:00,152 [INFO]: (tavern.core:55) Running test : Get some fake data from the JSON placeholder API
2017-11-08 16:17:00,153 [INFO]: (tavern.core:69) Running stage : Make sure we have the right ID
2017-11-08 16:17:00,239 [INFO]: (tavern.core:73) Response: '<Response [200]>' ({
  "userId": 1,
  "id": 1,
  "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
  "json": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
})
2017-11-08 16:17:00,239 [INFO]: (tavern.printer:9) PASSED: Make sure we have the right ID [200]
```

## Why not Postman, Insomnia or pyresttest etc?

Tavern is a focused tool which does one thing well: automated testing of
APIs.

**Postman** and **Insomnia** are excellent tools which cover a wide
range of use-cases for RESTful APIs, and indeed we use Tavern alongside
Postman. However, specifically with regards to automated testing, Tavern
has several advantages over Postman:

- A full-featured Python environment for writing easily reusable custom validation functions
- Testing of MQTT based systems in tandem with RESTful APIS.
- Seamless integration with pytest to keep all your tests in one place
- A simpler, less verbose and clearer testing language

Tavern does not do many of the things Postman and Insomnia do. For
example, Tavern does not have a GUI nor does it do API monitoring or
mock servers. On the other hand, Tavern is free and open-source and is a
more powerful tool for developers to automate tests.

**pyresttest** is a similar tool to Tavern for testing RESTful APIs, but
is no longer actively developed. On top of MQTT testing, Tavern has
several other advantages over PyRestTest which overall add up to a
better developer experience:

- Cleaner test syntax which is more intuitive, especially for
  non-developers
- Validation function are more flexible and easier to use
- Better explanations of why a test failed

## Hacking on Tavern

If you want to add a feature to Tavern or just play around with it
locally, it's a good plan to first create a local development
environment ([this
page](http://docs.python-guide.org/en/latest/dev/virtualenvs/) has a
good primer for working with development environments with Python).
After you've created your development environment, just
`pip install tox` and run `tox` to run the unit tests. If you want
to run the integration tests, make sure you have
[docker](https://www.docker.com/) installed and run
`tox -c tox-integration.ini` (bear in mind this might take a while.)
It's that simple!

If you want to develop things in tavern, enter your virtualenv and run
`pip install -r requirements.txt` to install the library, any requirements,
and other useful development options.

Tavern uses [ruff](https://pypi.org/project/ruff/) to keep all of the code
formatted consistently. There is a pre-commit hook to run `ruff format` which can
be enabled by running `pre-commit install`.

If you want to add a feature to get merged back into mainline Tavern:

- Add the feature you want
- Add some tests for your feature:
    - If you are adding some utility functionality such as improving verification
      of responses, adding some unit tests might be best. These are in the
      `tests/unit/` folder and are written using Pytest.
    - If you are adding more advanced functionality like extra validation
      functions, or some functionality that directly depends on the format of the
      input YAML, it might also be useful to add some integration tests. At the
      time of writing, this is done by adding an example flask endpoint in
      `tests/integration/server.py` and a corresponding Tavern YAML test file in
      the same directory. This will be cleaned up a bit once we have a proper
      plugin system implemented.
- Open a [pull request](https://github.com/taverntesting/tavern/pulls).

See [CONTRIBUTING.md](/CONTRIBUTING.md) for more details.

## Acknowledgements

Tavern makes use of several excellent open-source projects:

- [pytest](https://docs.pytest.org/en/latest/), the testing
  framework Tavern intergrates with
- [requests](http://docs.python-requests.org/en/master/), for HTTP
  requests
- [YAML](http://yaml.org/) and
  [pyyaml](https://github.com/yaml/pyyaml), for the test syntax
- [pykwalify](https://github.com/Grokzen/pykwalify), for YAML schema
  validation
- [pyjwt](https://github.com/jpadilla/pyjwt), for decoding JSON Web
  Tokens
- [colorlog](https://github.com/borntyping/python-colorlog), for
  formatting terminal outputs
- [paho-mqtt](https://github.com/eclipse/paho.mqtt.python), for
  sending MQTT messages

## Maintenance

Tavern is currently maintained by

- @michaelboulton
