# Changelog

# 0.1.0 - Initial release

## 0.1.2 - Allow sending/validation of JSON lists

## 0.1.3 - Fix global configuration loading via pytest command line

## 0.1.4 - Fix global configuration if it wasn't actually passed

## 0.1.5 - Fix temporary file wrapping on windows

# 0.2.0 - Add python 2 support

## 0.2.1 - Add option to install 'pytest' extra

## 0.2.2 - Support for 'verify' arg to requests

## 0.2.3 - quote nested json in query parameters

## 0.2.4 - Fix log format interpolation for py2

## 0.2.5 - Fix empty yaml files hard-failing

# 0.3.0 - Use a persistent requests Session to allow cookies to be propagated forward through tests

# 0.4.0 - MQTT support

# 0.5.0 - Add special 'tavern' key for formatting magic variables, and don't strictly enforce some HTTP verbs not having a body

## 0.5.1 - Add regex validation function and verify tests at run time, not discovery time

## 0.5.2 - Add MQTT TLS support and fixes to formatting nested arrays/dicts

## 0.5.3 - Update README

## 0.5.4 - Add 'meta' key to request block

currently the only key in 'meta' is clear_session_cookies which wipes the session cookies before the request is made

# 0.6.0 - Allow multiple global config options on the command line and in pytest config file

## 0.6.1 - Fix implementation of 'auth' keyword

# 0.7.0 - Add new 'anything' constructor for matching any value returned which should now also work with nested values. Also add special constructors for int/float types

## 0.7.1 - fix delay_after/before to accept float arguments

## 0.7.2 - Fix warning on incorrect status codes

## 0.7.3 - Improve error handling in parser errors

## 0.7.4 - Fix python 2

## 0.7.5 - Fix pytest-pspec error

## 0.7.6 - Move dict utilities around

## 0.7.7 - Improve validation on the type of block returned

# 0.8.0 - Fix matching magic variables and add new type sentinels for matching

## 0.8.1 - Fix formatting env vars into included variables

## 0.8.2 - Cleanup of type conversion code and better list item validation

# 0.9.0 - Add file upload capability

## 0.9.1 - Fix logging library warning

## 0.9.10 - Add new tag to match floating point numbers approximately in responses

## 0.9.2 - Minor improvement to error messages

## 0.9.3 - Improve error reporting from dictionary mismatches and allow regex checks in headers

## 0.9.4 - Fixes to type conversion tags, and add a new 'anybool' type sentinel to match either True or False

## 0.9.5 - Fix type conversion tokens and add more robust integration tests for them

## 0.9.6 - Add bool conversion type token as well

## 0.9.7 - Fix error in formatting MQTT variables

## 0.9.8 - Fix tavern overriding content type header when sending a file with extra headers

## 0.9.9 - Allow nesting of variables in included files that can be access using dot notation

# 0.10.0 - Add basic plugin system

## 0.10.1 - Slightly improve docstrings for use with pytest-pspec

## 0.10.2 - Fix python 2 type token issue

# 0.11.0 - Marking, strict key checking, and multiple status codes

- Add ability to use custom QoS for subscribing in MQTT
- Add pytest marks to tests
- Add strict key checking controllable by cli/per test
- Add verification for multiple status codes
- Improve 'doc' of test for pytest-pspec
- Add internal xfail for testing Tavern

# 0.12.0          Add parametrize mark and make run() use pytest.main in the background

See https://github.com/taverntesting/tavern/issues/127#issuecomment-398409023

calling run() directly will now cause a pytest isntance to be run in the background. This is to avoid having to maintain code and documentation for two separate entry points

## 0.12.1          Flesh out the 'run' function a bit more so it can mostly be used to pass in all config values without having to have a Pytest config file

## 0.12.2          Fix Pylint

## 0.12.3          Fix extra expected keys beign ignroed in responses sometimes

## 0.12.4          Fix case matching with headers

# 0.13.0          Add new flag to enable 'fancy' formatting on errors

## 0.13.1          Fix python 2 error

## 0.13.2          Bug fixes to logging and parametrization

## 0.13.3          Fix new traceback errors when anystr/anybool/etc was used

## 0.13.4          Fix to formatting empty bodies in response with new traceback

## 0.13.5          Fix for Python 2 regex function

# 0.14.0          Allow sending of raw data in the 'data' key for a HTTP request

## 0.14.3          Fix header value comparisons

## 0.14.4          Pylint fix

## 0.14.5          Add support for the 'stream' requests flag

# 0.15.0          Add basic pytest fixture support

## 0.15.1          Fix boolean conversion with anybool tag

## 0.15.2          Travis deployment fix

# 0.16.0          Add 'raw' token to alow using curly braces in strings

## 0.16.1          fix delay before/after bug

## 0.16.5          Fixes to requirements for development and working from local pypi indexes

# 0.17.0          Add support for putting stages in included files which can be referred to by an id

See 57f2a10e58a88325c185258d2c83b07a532aa93a for details

## 0.17.2          Stop wrapping responses/schemas in files for verification

# 0.18.0          Add 'timeout' parameter for http requests

## 0.18.1    Upload the content type along with the file if we can guess it

## 0.18.2          Fix formatting environment variables in command line global config files

## 0.18.3          Fix 'anything' token in included test stages

# 0.19.0          add retries to stages

## 0.19.1          fix typo in jmes utils

# 0.20.0          allow compatibility with pytest 4

# 0.21.0          add parametrisation of multiple keys without creating combinations

## 0.21.1          improve reporting of actual vs expected types in errors

# 0.22.0          fix selection of tests when using run() function interface

## 0.22.1          allow referenced stages to be included from global configuration files

# 0.23.0          Fix 'only' keyword

# 0.24.0          Fix typetoken validation and correctly unsubscribe from MQTT topics after a stage

# 0.25.0          Allow specifying custom SSL certificates in HTTP requests

## 0.25.1          Fix fancy traceback when comments in yaml files contain special characters

# 0.26.0          Add more advanced cookie behaviour

## 0.26.1          Fix matching 'anything' type token in MQTT

## 0.26.2          Fix loading global config via run function

## 0.26.3          Fix raw token formatting

## 0.26.4          Allow loading of json files using include directive

## 0.26.5          Lock pytest version to stop internal error

# 0.27.0

- Fix various typos in documentation
- Allow sending form data and files in a single request
- Fix double formatting of some string causing issues
- Add a global and stage specific flag to tell Tavern to not always follow redirects
- Fix not being able to use type tokens to format MQTT port
- Allow sending single values as JSON body as according to RFC 7159
- Change 'save' selector to use JMESpath

# 0.28.0

Add a couple of initial hooks

The initial 2 hooks should allow a user to do something before every test and
after every stage

# 0.29.0

Allow saving in MQTT tests and move calling external verification functions into their own block

# 0.30.0

Allow formatting of cookie names and allow overriding cookie values in a request

## 0.30.1

Fix MQTT subscription race condition

## 0.30.2

Fix parsing auth header

## 0.30.3

Fix marker serialisation for pytest-xdist

# 0.31.0

- Add isort
- Fix pytest warnings from None check
- Add warning when trying to coerce a non-stirnginto a string in string formatting
- Fix jmespath not working when the expected response was falsy
- Fix compatability with pytest-rerunfailures
- Add options to specify custom content type and encoding for files

# 0.32.0

Add option to control which files to search for rather than having it hardcoded

# 0.33.0

Add extra type tokens for matching arbitrary lists and dicts

# 0.34.0

Add new magic tag that includes something as json rather than a string


# 1.0.0

- 'body' key changes to 'json' in HTTP response

- Python 2 dropped

- Changes to the way strictness works

- remove 'null' checking on body matching anything

- 'run' entry point slightly reworked

- New error traceback is the default

- External function blocks changes

- Save value path changes to jmespath

-    Add key to allow uploading the raw content of a file as a request body

-    Add new token which can match regex values in parts of responses

-    Strict key checking should now work with MQTT json payloads

- Fix bug where saved variables were not cleared between tests

See https://github.com/taverntesting/tavern/issues/495 for details
