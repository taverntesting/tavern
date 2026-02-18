# Including and reusing data in tests

## Reusing requests and YAML fragments

A lot of tests will require using the same step multiple times, such as logging
in to a server before running tests or simply running the same request twice in
a row to make sure the same (or a different) response is returned.

Anchors are a feature of YAML which allows you to reuse parts of the code. Define
an anchor using  `&name_of_anchor`. This can then be assigned to another object
using `new_object: *name_or_anchor`, or they can be used to extend objects using
`<<: *name_of_anchor`.

```yaml
# input.yaml
---
first: &top_anchor
  a: b
  c: d

second: *top_anchor

third:
  <<: *top_anchor
  c: overwritten
  e: f
```

If we convert this to JSON, for example with a script like this:

```python
#!/usr/bin/env python

# load.py
import yaml
import json

with open("input.yaml", "r") as yfile:
    for doc in yaml.load_all(yfile.read()):
        print(json.dumps(doc, indent=2))
```

We get something like the following:

```
{
  'first': {
    'a': 'b',
    'c': 'd'
  },
  'second': {
    'a': 'b',
    'c': 'd'
  },
  'third': {
    'a': 'b',
    'c': 'overwritten',
    'e': 'f'
  }
}
```

This does not however work if there are different documents in the yaml file:

```yaml
# input.yaml
---
first: &top_anchor
  a: b
  c: d

second: *top_anchor

---

third:
  <<: *top_anchor
  c: overwritten
  e: f
```

```
$ python test.py
{
  "second": {
    "c": "d",
    "a": "b"
  },
  "first": {
    "c": "d",
    "a": "b"
  }
}
Traceback (most recent call last):
  File "test.py", line 8, in <module>
    for doc in yaml.load_all(yfile.read()):
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/__init__.py", line 84, in load_all
    yield loader.get_data()
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/constructor.py", line 31, in get_data
    return self.construct_document(self.get_node())
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 27, in get_node
    return self.compose_document()
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 55, in compose_document
    node = self.compose_node(None, None)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 84, in compose_node
    node = self.compose_mapping_node(anchor)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 133, in compose_mapping_node
    item_value = self.compose_node(node, item_key)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 84, in compose_node
    node = self.compose_mapping_node(anchor)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 133, in compose_mapping_node
    item_value = self.compose_node(node, item_key)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 69, in compose_node
    % anchor, event.start_mark)
yaml.composer.ComposerError: found undefined alias 'top_anchor'
  in "<unicode string>", line 12, column 7:
      <<: *top_anchor
```

This poses a bit of a problem for running our integration tests. If we want to
log in at the beginning of each test, or if we want to query some user
information which is then operated on for each test, we don't want to copy paste
the same code within the same file.

For this reason, Tavern will override the default YAML behaviour and preserve anchors
across documents **within the same file**. Then we can do something more like this:

```yaml
---
test_name: Make sure user location is correct

stages:
  - &test_user_login_anchor
    # Log in as user and save the login token for future requests
    name: Login as test user
    request:
      url: http://test.server.com/user/login
      method: GET
      json:
        username: test_user
        password: abc123
    response:
      status_code: 200
      save:
        json:
          test_user_login_token: token
      verify_response_with:
        function: tavern.helpers:validate_jwt
        extra_kwargs:
          jwt_key: "token"
          options:
            verify_signature: false

  - name: Get user location
    request:
      url: http://test.server.com/locations
      method: GET
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200
      json:
    location:
      road: 123 Fake Street
      country: England

---
test_name: Make sure giving premium works

stages:
  # Use the same block to log in across documents
  - *test_user_login_anchor

  - name: Assert user does not have premium
    request: &has_premium_request_anchor
      url: http://test.server.com/user_info
      method: GET
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200
      json:
        has_premium: false

  - name: Give user premium
    request:
      url: http://test.server.com/premium
      method: POST
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200

  - name: Assert user now has premium
    request:
      # Use the same block within one document
      <<: *has_premium_request_anchor
    response:
      status_code: 200
      json:
        has_premium: true
```

## Including external files

Even with being able to use anchors within the same file, there is often some
data which either you want to keep in a separate (possibly autogenerated) file,
or is used on every test (e.g. login information). You might also want to run the
same tests with different sets of input data.

Because of this, external files can also be included which contain simple
key: value data to be used in other tests.

Including a file in every test can be done by using a `!include` directive:

```yaml
# includes.yaml
---

# Each file should have a name and description
name: Common test information
description: Login information for test server

# Variables should just be a mapping of key: value pairs
variables:
  protocol: https
  host: www.server.com
  port: 1234
```

```yaml
# tests.tavern.yaml
---
test_name: Check server is up

includes:
  - !include includes.yaml

stages:
  - name: Check healthz endpoint
    request:
      method: GET
      url: "{protocol:s}://{host:s}:{port:d}"
    response:
      status_code: 200
```

As long as includes.yaml is in the same folder as the tests or found in the
TAVERN_INCLUDE search path, the variables will
automatically be loaded and available for formatting as before. Multiple include
files can be specified.

The environment variable TAVERN_INCLUDE can contain a : separated list of
paths to search for include files. Each path in TAVERN_INCLUDE has
environment variables expanded before it is searched.

### Including global configuration files

If you do want to run the same tests with a different input data, this can be
achieved by passing in a global configuration.

Using a global configuration file works the same as implicitly including a file
in every test. For example, say we have a server that takes a user's name and
address and returns some hash based on this information. We have two
servers that need to do this correctly, so we need two tests that use the same
input data but need to post to 2 different urls:

```yaml
# two_tests.tavern.yaml
---
test_name: Check server A responds properly

includes:
  - !include includesA.yaml

stages:
  - name: Check thing is processed correctly
    request:
      method: GET
      url: "{host:s}/"
      json: &input_data
        name: "{name:s}"
        house_number: "{house_number:d}"
        street: "{street:s}"
        town: "{town:s}"
        postcode: "{postcode:s}"
        country: "{country:s}"
        planet: "{planet:s}"
        galaxy: "{galaxy:s}"
        universe: "{universe:s}"
    response:
      status_code: 200
      json:
        hashed: "{expected_hash:s}"

---
test_name: Check server B responds properly

includes:
  - !include includesB.yaml

stages:
  - name: Check thing is processed correctly
    request:
      method: GET
      url: "{host:s}/"
      json:
        <<: *input_data
    response:
      status_code: 200
      json:
        hashed: "{expected_hash:s}"
```

Including the full set of input data in includesA.yaml and includesB.yaml would
mean that a lot of the same input data would be repeated. To get around this, we
can define a file called, for example, `common.yaml` which has all the input
data except for `host` in it, and make sure that includesA/B only have the
`host` variable in:

```yaml
# common.yaml
---

name: Common test information
description: |
  user location information for Joe Bloggs test user

variables:
  name: Joe bloggs
  house_number: 123
  street: Fake street
  town: Chipping Sodbury
  postcode: BS1 2BC
  country: England
  planet: Earth
  galaxy: Milky Way
  universe: A
  expected_hash: aJdaAK4fX5Waztr8WtkLC5
```

```yaml
# includesA.yaml
---

name: server A information
description: server A specific information

variables:
  host: www.server-a.com
```

```yaml
# includesB.yaml
---

name: server B information
description: server B specific information

variables:
  host: www.server-B.io
```

If the behaviour of server A and server B ever diverge in future, information
can be moved out of the common file and into the server specific include
files.

Using the `tavern-ci` tool or pytest, this global configuration can be passed in
at the command line using the `--tavern-global-cfg` flag. The variables in
`common.yaml` will then be available for formatting in *all* tests during that
test run.

**NOTE**: `tavern-ci` is just an alias for `py.test` and
will take the same options.

```
# These will all work
$ tavern-ci --tavern-global-cfg=integration_tests/local_urls.yaml
$ tavern-ci --tavern-global-cfg integration_tests/local_urls.yaml
$ py.test --tavern-global-cfg=integration_tests/local_urls.yaml
$ py.test --tavern-global-cfg integration_tests/local_urls.yaml
```

It might be tempting to put this in the 'addopts' section of the pytest.ini file
to always pass a global configuration when using pytest, but be careful when
doing this - due to what appears to be a bug in the pytest option parsing, this
might not work as expected:

```ini
# pytest.ini
[pytest]
addopts =
# This will work
    --tavern-global-cfg=integration_tests/local_urls.yaml
# This will not!
# --tavern-global-cfg integration_tests/local_urls.yaml
```

Instead, use the `tavern-global-cfg` option in your pytest.ini file:

```ini
[pytest]
tavern-global-cfg =
    integration_tests/local_urls.yaml
```

### Multiple global configuration files

Sometimes you will want to have 2 (or more) different global configuration
files, one containing common information such as paths to different resources
and another containing information specific to the environment that is being
tested. Multiple global configuration files can be specified either on the
command line or in pytest.ini to avoid having to put an `!include` directive in
every test:

```
# Note the '--' after all global configuration files are passed, indicating that
# arguments after this are not global config files
$ tavern-ci --tavern-global-cfg common.yaml test_urls.yaml -- test_server.tavern.yaml
$ py.test --tavern-global-cfg common.yaml local_docker_urls.yaml -- test_server.tavern.yaml
```

```ini
# pytest.ini
[pytest]
tavern-global-cfg =
    common.yaml
    test_urls.yaml
```

### Sharing stages in configuration files

If you have a stage that is shared across a huge number of tests and it
is infeasible to put all the tests which share that stage into one file,
you can also define stages in configuration files and use them in your
tests.

Say we have a login stage that needs to be run before every test in our
test suite. Stages are defined in a configuration file like this:

```yaml
# auth_stage.yaml
---

name: Authentication stage
description:
  Reusable test stage for authentication

variables:
  user:
    user: test-user
    pass: correct-password

stages:
  - id: login_get_token
    name: Login and acquire token
    request:
      url: "{service:s}/login"
      json:
        user: "{user.user:s}"
        password: "{user.pass:s}"
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      headers:
        content-type: application/json
      save:
        json:
          test_login_token: token
```

Each stage should have a uniquely identifiable `id`, but other than that
the stage can be define just as other tests (including using format
variables).

This can be included in a test by specifying the `id` of the test like
this:

```yaml
---

test_name: Test authenticated /hello

includes:
  - !include auth_stage.yaml

stages:
  - type: ref
    id: login_get_token
  - name: Authenticated /hello
    request:
      url: "{service:s}/hello/Jim"
      method: GET
      headers:
        Content-Type: application/json
        Authorization: "Bearer {test_login_token}"
    response:
      status_code: 200
      headers:
        content-type: application/json
      json:
        data: "Hello, Jim"

```

### Directly including test data

If your test just has a huge amount of data that you would like to keep
in a separate file, you can also (ab)use the `!include` tag to directly
include data into a test. Say we have a huge amount of JSON that we want
to send to a server and we don't want hundreds of lines in the test:

```json
// test_data.json
[
  {
    "_id": "5c965b1373f3fe071a9cb2b7",
    "index": 0,
    "guid": "ef3f8c42-522a-4d6b-84ec-79a07009460d",
    "isActive": false,
    "balance": "$3,103.47",
    "picture": "http://placehold.it/32x32",
    "age": 26,
    "eyeColor": "green",
    "name": "Cannon Wood",
    "gender": "male",
    "company": "CANDECOR",
    "email": "cannonwood@candecor.com",
    "phone": "+1 (944) 549-2826",
    "address": "528 Woodpoint Road, Snowville, Kansas, 140",
    "about": "Dolore in consequat exercitation esse esse velit eu velit aliquip ex. Reprehenderit est consectetur excepteur sint sint dolore. Anim minim dolore est ut fugiat. Occaecat tempor tempor mollit dolore anim commodo laboris commodo aute quis ex irure voluptate. Sunt magna tempor veniam cillum exercitation quis minim est eiusmod aliqua.\r\n",
    "registered": "2015-12-27T11:30:18 -00:00",
    "latitude": -2.515302,
    "longitude": -98.678105,
    "tags": [
      "proident",
      "aliqua",
      "velit",
      "labore",
      "consequat",
      "esse",
      "ea"
    ],
    "friends": [
      {
        "id": 0,
        "etc": []
      }
    ]
  }
]
```

(Handily generated by [JSON Generator](https://www.json-generator.com/))

Putting this whole thing into the test would be a bit overkill, but it
can be inject directly into your test like this:

```yaml
---

test_name: Post a lot of data

stages:
  - name: Create new user
    request:
      url: "{service:s}/new_user"
      method: POST
      json: !include test_data.json
    response:
      status_code: 201
      json:
        status: user created
```

This works with YAML as well, the only caveat being that the filename
_must_ end with `.yaml`, `.yml`, or `.json`.

## Including raw JSON data

Sometimes there are situations where you need to directly include a block of
JSON, such as a list, rather than just one value. To do this, there is a
`!force_original_structure` tag which will include whatever variable is being
referenced in the format block rather than coercing it to a string.

For example, if we have an API that will return a list of users on a GET and
will bulk delete a list of users on a DELETE, a test that all users are deleted
could be done by

1. GET all users

2. DELETE the list you just got

3. GET again and expect an empty list

```yaml
  - name: Get all users
    request:
      url: "{host}/users"
      method: GET
    response:
      status_code: 200
      # Expect a list of users
      json: !anylist
      save:
        json:
          # Save the list as 'all_users'
          all_users: "@"

  - name: delete all users
    request:
      url: "{host}/users"
      method: DELETE
      # 'all_users' list will be sent in the request as a list, not a string
      json: !force_original_structure "{all_users}"
    response:
      status_code: 204

  - name: Get no users
    request:
      url: "{host}/users"
      method: GET
    response:
      status_code: 200
      # Expect no users
      json: [ ]
```

Any blocks of JSON that are included this way will not be recursively formatted.
When using this token, do not use a conversion specifier (eg "{all_users:s}") as
it will be ignored.
