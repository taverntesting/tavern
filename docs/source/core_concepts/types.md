# Strict key checking

'Strict' key checking can be enabled or disabled globally, per test, or per
stage. 'Strict' key checking refers to whether extra keys in the response should
be ignored or whether they should raise an error. With strict key checking
enabled, all keys in dictionaries at all levels have to match or it will raise
an error. With it disabled, Extra keys in the response will be ignored as long
as the ones in your response block are present.

Strict key checking can be controlled individually for the response for the JSON
body,the redirect query parameter, or the headers.

By default, strict key checking is _disabled_ for headers and redirect query
parameters in the response, but _enabled_ for JSON (as well as when checking for
JSON in an mqtt response). This is because although there may be a lot of
'extra' things in things like the response headers (such as server agent
headers, cache control headers, etc), the expected JSON body will likely always
want to be matched exactly.

### Effect of different settings

This is best explained through an example. If we expect this response from a
server:

```json
{
  "first": 1,
  "second": {
    "nested": 2
  }
}
```

This is what we would put in our Tavern test:

```yaml
...
response:
  json:
    first: 1
    second:
      nested: 2
```

The behaviour of various levels of 'strictness' based on the response:

| Response                                                  | strict=on | strict=off |
|-----------------------------------------------------------|-----------|------------|
| `{ "first": 1, "second": { "nested": 2 } }`               | PASS      | PASS       |
| `{ "first": 1 }`                                          | FAIL      | PASS       |
| `{ "first": 1, "second": { "another": 2 } }`              | FAIL      | FAIL       |
| `{ "first": 1, "second": { "nested": 2, "another": 2 } }` | FAIL      | PASS       |

Turning 'strict' off also means that extra items in lists will be ignored as
long as the ones specified in the test response are present. For example, if the
response from a server is `[ 1, 2, 3 ]` then strict being on - the default for
the JSON response body - will match _only_ `[1, 2, 3]`.

With strict being turned off for the body, any of these in the test will pass:

- `[1, 2, 3]`
- `[1]`
- `[2]`
- `[3]`
- `[1, 2]`
- `[2, 3]`
- `[1, 3]`

But not:

- `[2, 4]` - '4' not present in response from the server
- `[3, 1]`, `[2, 1]` - items present, but out of order

To match the last case you can use the special setting `list_any_order`. This setting
can only be used in the 'json' key of a request, but will match list items in any order as
long as they are present in the response.

### Changing the setting

This setting can be controlled in 3 different ways, the order of priority being:

1. In the test/stage itself
2. Passed on the command line
3. Read from pytest config

This means that using the command line option will _not_ override any settings
for specific tests.

Each of these methods is done by passing a sequence of strings indicating which
section (`json`/`redirect_query_params`/`headers`) should be affected, and
optionally whether it is on or off.

- `json:off headers:on` - turn off for the body, but on for the headers.
  `redirect_query_params` will stay default off.
- `json:off headers:off` - turn body and header strict checking off
- `redirect_query_params:on json:on` redirect parameters is turned on and json
  is kept on (as it is on by default), header strict matching is kept off (as
  default).

Leaving the 'on' or 'off' at the end of each setting will imply 'on' - ie, using
`json headers redirect_query_params` as an option will turn them all on.

#### Command line

There is a command line argument, `--tavern-strict`, which controls the default
global strictness setting.

```shell
# Enable strict checking for body and headers only
py.test --tavern-strict json:on headers:on redirect_query_params:off -- my_test_folder/
```

#### In the Pytest config file

This behaves identically to the command line option, but will be read from
whichever configuration file Pytest is using.

```ini
[pytest]
tavern-strict = json:off headers:on
```

#### Per test

Strictness can also be enabled or disabled on a per-test basis. The `strict` key
at the top level of the test should a list consisting of one or more strictness
setting as described in the previous section.

```yaml
---

test_name: Make sure the headers match what I expect exactly

strict:
  - headers:on
  - json:off

stages:
  - name: Try to get user
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      status_code: 200
      headers:
        content-type: application/json
        content-length: 20
        x-my-custom-header: chocolate
      json:
        # As long as "id: 1" is in the response, this will pass and other keys will be ignored
        id: 1
```

A special option that can be done at the test level (or at the stage level, as
described in the next section) is just to pass a boolean. This will turn strict
checking on or off for all settings for the duration of that test/stage.

```yaml
test_name: Just check for one thing in a big nested dict

# completely disable strict key checking for this whole test
strict: False

stages:
  - name: Try to get user
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      status_code: 200
      json:
        q:
          x:
            z:
              a: 1
```

#### Per stage

Often you have a standard stage before other stages, such as logging in to your
server, where you only care if it returns a 200 to indicate that you're logged
in. To facilitate this, you can enable or disable strict key checking on a
per-stage basis as well.

Two examples for doing this - these examples should behave identically:

```yaml
---

# Enable strict checking for this test, but disable it for the login stage

test_name: Login and create a new user

# Force re-enable strict checking, in case it was turned off globally
strict:
  - json:on

stages:
  - name: log in
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      # Disable all strict key checking just for this stage
      strict: False
      status_code: 200
      json:
        logged_in: True
        # Ignores any extra metadata like user id, last login, etc.

  - name: Create a new user
    request:
      url: "{host}/users/joebloggs"
      method: POST
      json: &create_user
        first_name: joe
        last_name: bloggs
        email: joe@bloggs.com
    response:
      status_code: 200
      # Because strict was set 'on' at the test level, this must match exactly
      json:
        <<: *create_user
        id: 1
```

Or if strict json key checking was enabled at the global level:

```yaml
---

test_name: Login and create a new user

stages:
  - name: log in
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      strict:
        - json:off
      status_code: 200
      json:
        logged_in: True

  - name: Create a new user
    request: ...
```

## Matching arbitrary return values in a response

Sometimes you want to just make sure that a value is returned, but you don't
know (or care) what it is. This can be achieved by using `!anything` as the
value to match in the **response** block:

```yaml
response:
  json:
    # Will assert that there is a 'returned_uuid' key, but will do no checking
    # on the actual value of it
    returned_block: !anything
```

This would match both of these response bodies:

```yaml
returned_block: hello
```

```yaml
returned_block:
  nested: value
```

Using the magic `!anything` value should only ever be used inside pre-defined
blocks in the response block (for example, `headers`, `params`, and `json` for a
HTTP response).

**NOTE**: Up until version 0.7.0 this was done by setting the value as `null`.
This creates issues if you want to ensure that your server is actually returning
a null value. Using `null` is still supported in the current version of Tavern,
but will be removed in a future release, and should raise a warning.

### Matching arbitrary specific types in a response

If you want to make sure that the key returned is of a specific type, you can
use one of the following markers instead:

- `!anynumber`: Matches any number (integer or float)
- `!anyint`: Matches any integer
- `!anyfloat`: Matches any float (note that this will NOT match integers!)
- `!anystr`: Matches any string
- `!anybool`: Matches any boolean (this will NOT match `null`)
- `!anylist`: Matches any list
- `!anydict`: Matches any dict/'mapping'

### Matching via a regular expression

Sometimes you know something will be a string, but you also want to make sure
that the string matches some kind of regular expression. This can be done using
external functions, but as a shorthand there is also the `!re_` family of custom
YAML tags that can be used to match part of a response. Say that we want to make
sure that a UUID returned is a
[version 4 UUID](https://tools.ietf.org/html/rfc4122#section-4.1.3), where the
third block must start with 4 and the third block must start with 8, 9, "A", or
"B".

```yaml
  - name: Check that uuidv4 is returned
    request:
      url: { host }/get_uuid/v4
      method: GET
    response:
      status_code: 200
      json:
        uuid: !re_fullmatch "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89AB][0-9a-f]{3}-[0-9a-f]{12}"
```

This is using the `!re_fullmatch` variant of the tag - this calls
[`re.fullmatch`](https://docs.python.org/3.11/library/re.html#re.fullmatch) under
the hood, which means that the regex given needs to match the _entire_ part of
the response that is being checked for it to pass. There is also `!re_search`
which will pass if it matches _part_ of the thing being checked, or `!re_match`
which will match _part_ of the thing being checked, as long as it is at the
_beginning_ of the string. See the Python documentation for more details.

Another way of doing this is to use the builtin `validate_regex` helper function.
For example if we want to get a version that is returned in a 'meta' key in the
format `v1.2.3-510c2665d771e1`:

```yaml
stages:
  - name: get a token by id
    request:
      url: "{host}/tokens/get"
      method: GET
      params:
        id: 456
    response:
      status_code: 200
      json:
        code: abc123
        id: 456
        meta:
          version: !anystr
          hash: 456
      save:
        $ext:
          function: tavern.helpers:validate_regex
          extra_kwargs:
            expression: "v(?P<version>[\d\.]+)-[\w\d]+"
            in_jmespath: "meta.version"
```

This is a more flexible version of the helper which can also be used to save values
as in the example. If a named matching group is used as shown above, the saved values
can then be accessed in subsequent stages by using the `regex.<group-name>` syntax, eg:

```yaml
- name: Reuse thing specified in first request
  request:
    url: "{host}/get_version_info"
    method: GET
    params:
      version: "{regex.version}"
  response:
    status_code: 200
    json:
      simple_version: "v{regex.version}"
      made_on: "2020-02-21"
```

## Type conversions

[YAML](http://yaml.org/spec/1.1/current.html#id867381) has some magic variables
that you can use to coerce variables to certain types. For example, if we want
to write an integer but make sure it gets converted to a string when it's
actually sent to the server we can do something like this:

```yaml
request:
  json:
    an_integer: !!str 1234567890
```

However, due to the way YAML is loaded this doesn't work when you are using a
formatted value. Because of this, Tavern provides similar special constructors
that begin with a *single* exclamation mark that will work with formatted
values. Say we want to convert a value from an included file to an integer:

```yaml
request:
  json:
    # an_integer: !!int "{my_integer:d}" # Error
    an_integer: !int "{my_integer:d}" # Works
```

Because curly braces are automatically formatted, trying to send one
in a string might cause some unexpected issues. This can be mitigated
by using the `!raw` tag, which will not perform string formatting.

*Note*: This is just shorthand for replacing a `{` with a `{{` in the
string

```yaml
request:
  json:
    # Sent as {"raw_braces": "{not_escaped}"}
    raw_braces: !raw "{not_escaped}"
```
