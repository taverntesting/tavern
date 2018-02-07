.. image:: https://travis-ci.org/taverntesting/tavern.svg?branch=master
    :target: https://travis-ci.org/taverntesting/tavern

.. image:: https://img.shields.io/pypi/v/tavern.svg
    :target: https://pypi.org/project/tavern/

Restful API testing
===================

Tavern is a pytest plugin, command-line tool and Python library for
automated testing of RESTful APIs, with a simple, concise and flexible
YAML-based syntax. It's very simple to get started, and highly
customisable for complex tests.

The best way to use Tavern is with
`pytest <https://docs.pytest.org/en/latest/>`__. Tavern comes with a
pytest plugin so that literally all you have to do is install pytest and
Tavern, write your tests in ``.tavern.yaml`` files and run pytest. This
means you get access to all of the pytest ecosystem and allows you to do
all sorts of things like regularly run your tests against a test server
and report failures or generate HTML reports.

You can also integrate Tavern into your own test framework or continuous
integration setup using the Python library, or use the command line
tool, ``tavern-ci`` with bash scripts and cron jobs.

To learn more, check out the `examples <https://taverntesting.github.io/examples>`__ or the complete
`documentation <https://taverntesting.github.io/documentation>`__. If you're interested in contributing
to the project take a look at the `GitHub
repo <https://github.com/taverntesting/tavern>`__.

Quickstart
----------

Note that Tavern **only** supports Python 2.7 and up, and at the time of writing is only
tested against Python 2.7/3.4-3.6.

::

    $ pip install tavern

.. code:: yaml

    # minimal_test.tavern.yaml

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
          body:
            id: 1

::

    $ tavern-ci --stdout minimal_test.tavern.yaml
    2017-11-08 16:17:00,152 [INFO]: (tavern.core:55) Running test : Get some fake data from the JSON placeholder API
    2017-11-08 16:17:00,153 [INFO]: (tavern.core:69) Running stage : Make sure we have the right ID
    2017-11-08 16:17:00,239 [INFO]: (tavern.core:73) Response: '<Response [200]>' ({
      "userId": 1,
      "id": 1,
      "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
      "body": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
    })
    2017-11-08 16:17:00,239 [INFO]: (tavern.printer:9) PASSED: Make sure we have the right ID [200]

Why not Postman, Insomnia or pyresttest etc?
--------------------------------------------

Tavern is a focused tool which does one thing well: automated testing of
RESTful APIs.

**Postman** and **Insomnia** are excellent tools which cover a wide
range of use-cases, and indeed we use Tavern alongside Postman. However,
specifically with regards to automated testing, Tavern has several
advantages over Postman: - A full-featured Python environment for
writing custom validation functions - Seamless integration with pytest
to keep all your tests in one place - A simpler, less verbose and
clearer testing language

Tavern does not do many of the things Postman and Insomnia do. For
example, Tavern does not have a GUI nor does it do API monitoring or
mock servers. On the other hand, Tavern is free and open-source and is a
more powerful tool for developers to automate tests.

**pyresttest** is similar to Tavern but is no longer actively developed.
Tavern also has several advantages over PyRestTest which overall add up
to a better developer experience:

-  Cleaner test syntax which is more intuitive, especially for
   non-developers
-  Validation function are more flexible and easier to use
-  Better explanations of why a test failed

Developed and maintained by Overlock
------------------------------------

Overlock helps developers quickly find and fix bugs in distributed systems such as IoT deployments by gathering together exception information from end devices, gateways or servers. We’re currently in beta - find out more at `overlock.io <https://overlock.io>`__.

Acknowledgements
----------------

Tavern makes use of several excellent open-source projects:

-  `pytest <https://docs.pytest.org/en/latest/>`__, the testing
   framework Tavern intergrates with
-  `requests <http://docs.python-requests.org/en/master/>`__, for HTTP
   requests
-  `YAML <http://yaml.org/>`__ and
   `pyyaml <https://github.com/yaml/pyyaml>`__, for the test syntax
-  `pykwalify <https://github.com/Grokzen/pykwalify>`__, for YAML schema
   validation
-  `pyjwt <https://github.com/jpadilla/pyjwt>`__, for decoding JSON Web
   Tokens
-  `colorlog <https://github.com/borntyping/python-colorlog>`__, for
   formatting terminal outputs
