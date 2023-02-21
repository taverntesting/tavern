# Examples

## 1) The simplest possible test

To show you just how simple a Tavern test can be, here's one which uses the JSON Placeholder API at [jsonplaceholder.typicode.com](https://jsonplaceholder.typicode.com/). To try it, create a new file called `test_minimal.tavern.yaml` with the following:

```yaml
test_name: Get some fake data from the JSON placeholder API

stages:
  - name: Make sure we have the right ID
    request:
      url: https://jsonplaceholder.typicode.com/posts/1
      method: GET
    response:
      status_code: 200
      json:
        id: 1
        userId: 1
        title: "sunt aut facere repellat provident occaecati excepturi optio reprehenderit"
        body: "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
```

Next, install Tavern if you have not already:

```bash
$ pip install tavern
```

In most circumstances you will be using Tavern with pytest but you can also run it using the Tavern command-line interface, `tavern-ci`, which is installed along with Tavern:

```bash
$ tavern-ci test_minimal.tavern.yaml
```

Run `tavern-ci --help` for more usage information.

Note that Tavern will only run tests from files whose names follow the pattern `test_*.tavern.yaml` (or `test_*.tavern.yml`) - for example, `test_minimal.tavern.yaml`, `test_another.tavern.yml`.

## 2) Testing a simple server

In this example we will create a server with a single route which doubles any number you pass it, and write some simple tests for it. You'll see how simple the YAML-based syntax can be, and the three different ways you can run Tavern tests.

Here's what such a server might look like:

```python
# server.py

from flask import Flask, jsonify, request
app = Flask(__name__)

@app.route("/double", methods=["POST"])
def double_number():
    r = request.get_json()

    try:
        number = r["number"]
    except (KeyError, TypeError):
        return jsonify({"error": "no number passed"}), 400

    try:
        double = int(number)*2
    except ValueError:
        return jsonify({"error": "a number was not passed"}), 400

    return jsonify({"double": double}), 200
```

Run the server using Flask:

```bash
$ export FLASK_APP=server.py
$ flask run
```

There are two key things to test here: first, that it successfully doubles
numbers and second, that it returns the correct error codes and messages. To do
this we will write two tests, one for the success case and one for the error
case. Each test can contain one or more stages, and each stage has a name, a
request and an expected response.

```yaml
# test_server.tavern.yaml

---

test_name: Make sure server doubles number properly

stages:
  - name: Make sure number is returned correctly
    request:
      url: http://localhost:5000/double
      json:
        number: 5
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      json:
        double: 10

---

test_name: Check invalid inputs are handled

stages:
  - name: Make sure invalid numbers don't cause an error
    request:
      url: http://localhost:5000/double
      json:
        number: dkfsd
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 400
      json:
        error: a number was not passed

  - name: Make sure it raises an error if a number isn't passed
    request:
      url: http://localhost:5000/double
      json:
        wrong_key: 5
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 400
      json:
        error: no number passed
```

The tests can be run in three different ways: from Python code, from the command line, or with pytest. The most common way is to use pytest. All three require Tavern to be installed.

If you run pytest in a folder containing `test_server.tavern.yaml` it will automatically find the file and run the tests. Otherwise, you will need to point it to the folder containing the integration tests or add it to `setup.cfg/tox.ini/etc` so that Pytest's collection mechanism knows where to look.

```bash
$ py.test
============================= test session starts ==============================
platform linux -- Python 3.5.2, pytest-3.2.0, py-1.4.34, pluggy-0.4.0
rootdir: /home/developer/project/tests, inifile: setup.cfg
plugins: tavern-0.0.1
collected 4 items

test_server.tavern.yaml ..

===================== 2 passed, 2 skipped in 0.07 seconds ======================
```

The command line tool is useful for bash scripting, for example if you want to verify that an API is works before deploying it, or for cron jobs.

```bash
$ tavern-ci test_server.tavern.yaml
$ echo $?
0
```

The Python library allows you to include Tavern tests in deploy scripts written in Python, or for use with a continuous integration setup:

```python
from tavern.core import run
from pytest import ExitCode

exit_code = run("test_server.tavern.yaml")

if exit_code != ExitCode.OK:
    print("Error running tests")
```

See the documentation section on global configuration for use of the second
argument.

## 3) Multi-stage tests

The final example uses a more complex test server which requires the user to log in, save the token it returns and use it for all future requests. It also has a simple database so we can check that data we send to it is successfully returned.

[Here is the example server we will be using.](/server)

To test this behaviour we can use multiple tests in a row, keeping track of variables between them, and ensuring the server state has been updated as expected.

```yaml
test_name: Make sure server saves and returns a number correctly

stages:
  - name: login
    request:
      url: http://localhost:5000/login
      json:
        user: test-user
        password: correct-password
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      json:
        $ext:
          function: tavern.helpers:validate_jwt
          extra_kwargs:
            jwt_key: "token"
            key: CGQgaG7GYvTcpaQZqosLy4
            options:
              verify_signature: true
              verify_aud: false
      headers:
        content-type: application/json
      save:
        json:
          test_login_token: token

  - name: post a number
    request:
      url: http://localhost:5000/numbers
      json:
        name: smallnumber
        number: 123
      method: POST
      headers:
        content-type: application/json
        Authorization: "bearer {test_login_token:s}"
    response:
      status_code: 201
      json:
        {}
      headers:
        content-type: application/json

  - name: Make sure its in the db
    request:
      url: http://localhost:5000/numbers
      params:
        name: smallnumber
      method: GET
      headers:
        content-type: application/json
        Authorization: "bearer {test_login_token:s}"
    response:
      status_code: 200
      json:
        number: 123
      headers:
        content-type: application/json
```

This example illustrates three major parts of the Tavern syntax: saving data, using that data in later requests and using validation functions.

## Further reading

There are more examples in the [examples](https://github.com/taverntesting/tavern/tree/master/example) folder on Github, showing how to do some more advanced testing, including how to test using MQTT. Tavern also has a lot of integration tests that show its behaviour - you might find it useful to check out the [integration tests](https://github.com/taverntesting/tavern/tree/master/tests/integration) folder for some more examples.

To see the source code, suggest improvements or even contribute a pull request check out the [GitHub repository](https://github.com/taverntesting/tavern).
