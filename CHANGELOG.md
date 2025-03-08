# Changelog

##  0.1.2           Allow sending/validation of JSON lists (2017-11-21)

##  0.1.3           Fix global configuration loading via pytest command line (2017-12-05)

##  0.1.4           Fix global configuration if it wasn't actually passed (2017-12-06)

##  0.1.5           Fix temporary file wrapping on windows (2017-12-06)

#  0.2.0           Add python 2 support (2017-12-12)

##  0.2.1           Add option to install 'pytest' extra (2017-12-12)

##  0.2.2           Support for 'verify' arg to requests (2018-01-23)

##  0.2.3           quote nested json in query parameters (2018-01-23)

##  0.2.4           Fix log format interpolation for py2 (2018-01-25)

##  0.2.5           Fix empty yaml files hard-failing (2018-01-25)

#  0.3.0           Use a persistent requests Session to allow cookies to be propagated forward through tests (2018-02-15)

#  0.4.0           MQTT support (2018-02-22)

#  0.5.0           Add special 'tavern' key for formatting magic variables, and don't strictly enforce some HTTP verbs not having a body (2018-02-23)

##  0.5.1           Add regex validation function and verify tests at run time, not discovery time (2018-02-26)

##  0.5.2           Add MQTT TLS support and fixes to formatting nested arrays/dicts (2018-03-05)

##  0.5.3           Update README (2018-03-05)

##  0.5.4           Add 'meta' key to request block (2018-03-05)


currently the only key in 'meta' is clear_session_cookies which wipes the session cookies before the request is made

#  0.6.0           Allow multiple global config options on the command line and in pytest config file (2018-03-07)

##  0.6.1           Fix implementation of 'auth' keyword (2018-03-09)

#  0.7.0           Add new 'anything' constructor for matching any value returned which should now also work with nested values. Also add special constructors for int/float types (2018-03-09)

##  0.7.1           fix delay_after/before to accept float arguments (2018-03-12)

##  0.7.2           Fix warning on incorrect status codes (2018-03-20)

##  0.7.3           Improve error handling in parser errors (2018-03-21)

##  0.7.4           Fix python 2 (2018-03-21)

##  0.7.5           Fix pytest-pspec error (2018-03-21)

##  0.7.6           Move dict utilities around (2018-03-21)

##  0.7.7           Improve validation on the type of block returned (2018-03-23)

#  0.8.0           Fix matching magic variables and add new type sentinels for matching (2018-04-03)

##  0.8.1           Fix formatting env vars into included variables (2018-04-03)

##  0.8.2           Cleanup of type conversion code and better list item validation (2018-04-05)

#  0.9.0           Add file upload capability (2018-04-10)

##  0.9.1           Fix logging library warning (2018-04-11)

##  0.9.2           Minor improvement to error messages (2018-04-13)

##  0.9.3           Improve error reporting from dictionary mismatches and allow regex checks in headers (2018-05-04)

##  0.9.4           Fixes to type conversion tags, and add a new 'anybool' type sentinel to match either True or False (2018-05-15)

##  0.9.5           Fix type conversion tokens and add more robust integration tests for them (2018-05-16)

##  0.9.6           Add bool conversion type token as well (2018-05-16)

##  0.9.7           Fix error in formatting MQTT variables (2018-05-24)

##  0.9.8           Fix tavern overriding content type header when sending a file with extra headers (2018-05-25)

##  0.9.9           Allow nesting of variables in included files that can be access using dot notation (2018-05-29)

#  0.9.10          Add new tag to match floating point numbers approximately in responses (2018-05-29)

#  0.10.0          Add basic plugin system (2018-05-29)

##  0.10.1          Slightly improve docstrings for use with pytest-pspec (2018-06-11)

##  0.10.2          Fix python 2 type token issue (2018-06-13)

#  0.11.0          Marking, strict key checking, and multiple status codes (2018-06-18)


- Add ability to use custom QoS for subscribing in MQTT
- Add pytest marks to tests
- Add strict key checking controllable by cli/per test
- Add verification for multiple status codes
- Improve 'doc' of test for pytest-pspec
- Add internal xfail for testing Tavern

#  0.12.0          Add parametrize mark and make run() use pytest.main in the background (2018-06-20)


See https://github.com/taverntesting/tavern/issues/127#issuecomment-398409023

calling run() directly will now cause a pytest isntance to be run in the background. This is to avoid having to maintain code and documentation for two separate entry points

##  0.12.1          Flesh out the 'run' function a bit more so it can mostly be used to pass in all config values without having to have a Pytest config file (2018-06-20)

##  0.12.2          Fix Pylint (2018-06-20)

##  0.12.3          Fix extra expected keys beign ignroed in responses sometimes (2018-06-20)

##  0.12.4          Fix case matching with headers (2018-06-20)

#  0.13.0          Add new flag to enable 'fancy' formatting on errors (2018-06-21)

##  0.13.1          Fix python 2 error (2018-06-21)

##  0.13.2          Bug fixes to logging and parametrization (2018-06-22)

##  0.13.3          Fix new traceback errors when anystr/anybool/etc was used (2018-06-22)

##  0.13.4          Fix to formatting empty bodies in response with new traceback (2018-06-22)

##  0.13.5          Fix for Python 2 regex function (2018-06-25)

#  0.14.0          Allow sending of raw data in the 'data' key for a HTTP request (2018-06-27)

##  0.14.1          CI fix (2018-06-27)

##  0.14.2          CI fix (2018-06-27)

##  0.14.3          Fix header value comparisons (2018-07-04)

##  0.14.4          Pylint fix (2018-07-04)

##  0.14.5          Add support for the 'stream' requests flag (2018-07-06)

#  0.15.0          Add basic pytest fixture support (2018-07-10)

##  0.15.1          Fix boolean conversion with anybool tag (2018-07-11)

##  0.15.2          Travis deployment fix (2018-07-16)

#  0.16.0          Add 'raw' token to alow using curly braces in strings (2018-07-24)

##  0.16.1          fix delay_before/after bug (2018-07-26)

##  0.16.2          dummy bump tag for travis deploy (2018-07-26)

##  0.16.3          dummy bump tag for travis deploy (2018-07-26)

##  0.16.4          dummy bump tag for travis deploy (2018-07-26)

##  0.16.5          Fixes to requirements for development and working from local pypi indexes (2018-08-02)

#  0.17.0          Add support for putting stages in included files which can be referred to by an id - see 57f2a10e58a88325c185258d2c83b07a532aa93a for details (2018-08-04)

##  0.17.1          Dummy tag to attempt to make travis dpeloy, again (2018-08-07)

##  0.17.2          Stop wrapping responses/schemas in files for verification (2018-08-07)

#  0.18.0          Add 'timeout' parameter for http requests (2018-08-24)

##  0.18.1          Add content type/encoding to uploaded files (2018-09-05)

##  0.18.2          Fix formatting environment variables in command line global config files (2018-09-21)

##  0.18.3          Fix 'anything' token in included test stages (2018-09-28)

#  0.19.0          Add retries to stages (2018-10-07)

##  0.19.1          Fix typo in JMES utils (2018-10-14)

#  0.20.0          Allow compatibility with pytest 4 (2018-11-15)

#  0.21.0          Add parametrisation of multiple keys without creating combinations (2018-12-09)

##  0.21.1          Improve reporting of actual vs expected types in errors (2018-12-09)

#  0.22.0          Fix selection of tests when using run() function interface (2018-12-28)


This used pytests's -k flag when we actually wanted to change collection of tests, not collecting all tests then selecting by name

##  0.22.1          Allow referenced stages to be included from global configuration files (2018-12-28)

#  0.23.0          Fix 'only' keyword (2019-02-02)

#  0.24.0          Fix typetoken validation and correctly unsubscribe from MQTT topics after a stage (2019-02-16)

#  0.25.0          Allow specifying custom SSL certificates in HTTP requests (2019-02-21)

##  0.25.1          Fix fancy traceback when comments in yaml files contain special characters (2019-03-16)

#  0.26.0          Add more advanced cookie behaviour (2019-03-17)

##  0.26.1          Fix matching 'anything' type token in MQTT (2019-03-17)

##  0.26.2          Fix loading global config via run function (2019-03-19)

##  0.26.3          Fix raw token formatting (2019-04-11)

##  0.26.4          Allow loading of json files using include directive (2019-06-01)

##  0.26.5          Lock pytest version to stop internal error (2019-06-01)

#  0.27.0          0.27.0 release (2019-08-10)


- Fix various typos in documentation
- Allow sending form data and files in a single request
- Fix double formatting of some string causing issues
- Add a global and stage specific flag to tell Tavern to not always follow redirects
- Fix not being able to use type tokens to format MQTT port
- Allow sending single values as JSON body as according to RFC 7159
- Change 'save' selector to use JMESpath

#  0.28.0          Add a couple of initial hooks (2019-08-26)


The initial 2 hooks should allow a user to do something before every test and after every stage

#  0.29.0          Allow saving in MQTT tests and move calling external verification functions into their own block (2019-08-28)

#  0.30.0          Allow formatting of cookie names and allow overriding cookie values in a request (2019-08-30)

##  0.30.1          Fix MQTT subscription race condition (2019-09-07)

##  0.30.2          Fix parsing auth header (2019-09-07)

##  0.30.3          Fix marker serialisation for pytest-xdist (2019-09-07)

#  0.31.0          - Add isort (2019-11-22)

- Fix pytest warnings from None check
- Add warning when trying to coerce a non-stirnginto a string in string formatting
- Fix jmespath not working when the expected response was falsy
- Fix compatability with pytest-rerunfailures
- Add options to specify custom content type and encoding for files

#  0.32.0          Add option to control which files to search for rather than having it hardcoded (2019-11-22)

#  0.33.0          Add extra type tokens for matching lsits and dicts (2019-11-25)

#  0.34.0          Add new magic tag that includes something as json rather than a string (2019-12-08)

#  1.0.0           1.0 Release (2020-04-05)

##  1.0.1           Enable formatting of file body key in requests (2020-05-01)

##  1.0.2           Fix incorrect logic checking request codes (2020-05-01)

#  1.1.0           Add new global option to enable merging of keys from external functions (2020-05-01)

##  1.1.1           Travis fix (2020-05-23)

##  1.1.2           fforce new verison to make travis actually commit (2020-05-23)

##  1.1.3           travis (2020-05-23)

##  1.1.4           Bump version: 1.1.3 → 1.1.4 (2020-05-23)

##  1.1.5           travis (2020-05-23)

#  1.2.0           allow passing max_retries as a format variable (2020-05-25)

##  1.2.1           travis (2020-05-25)

##  1.2.2           travis (2020-05-25)

##  1.2.3           lock pytest to below 6 temporarily (2020-08-01)

##  1.2.4           Be more relaxed in locking dependency versions (2020-08-08)

#  1.3.0           Allow autouse fixtures in Tavern tests (2020-08-08)

#  1.4.0           Support pytest 6 (2020-08-15)

##  1.4.1           Fix reading utf8 encoded test files (2020-08-22)

#  1.5.0           Allow using environment variables when formatting test marks (2020-08-26)

##  1.5.1           Fix strictness for a stage 'leaking' into the subsequent stages (2020-08-26)

#  1.6.0           Allow specifying just the stage 'id' in case of a stage ref without also needing a name (2020-08-26)

#  1.7.0           Add TAVERN_INCLUDE_PATH to allow including files from other file locations (2020-10-09)

#  1.8.0           Move parametrize functions out of main class as they are specific behaviour (2020-10-09)


Add filterwarning to schema

#  1.10.0          Format filenames (#612) (2020-11-07)



#  1.11.0          523 add request hook (#615) (2020-11-07)



#  1.9.0           219 response function calls (#614) (2020-11-06)


Also log the result from 'response' ext functions

##  1.7.1           Bump max version of paho-mqtt (2020-11-07)

##  1.11.1          Fix bumped version (2020-11-07)

#  1.12.0          Allow ext functions in mqtt blocks (2020-12-11)

##  1.12.1          Fix pytest deprecation warning (2020-12-11)

##  1.12.2          lock pykwalify version to 1.7 because of breaking API change in 1.8 (2020-12-31)

#  1.13.0          Add support for generating Allure test reports (2021-01-30)

##  1.13.1          Fix using ext functions in query params (2021-01-30)

##  1.13.2          Fix checking for cert_reqs file (2021-02-20)

#  1.14.0          Add extra argument to regex helper to allow matching from a jmespath (2021-02-20)

##  1.14.1          Fix mqtt tls options validation (2021-03-27)

##  1.14.2          Stop pytest warning about a private import (2021-04-05)

#  1.15.0          Update pytest and pykwalify (2021-06-06)

#  1.16.0          Allow specifying a new strict option which will allow list items in any order (2021-06-20)

##  1.16.1          Fix regression in nested strict key checking (2021-09-05)

##  1.16.2          Fix some settings being lost after retrying a stage (2021-10-03)

##  1.16.3          Fix --collect-only flag (2021-10-17)

##  1.16.4          Change a couple of instances of logging where 'info' might log sensitive data and add note to docs (2021-10-31)

##  1.16.5          Fix 'x is not None' vs 'not x' causing strict matching error (2021-10-31)

#  1.17.0          Allow parametrising HTTP method (2021-10-31)

##  1.17.1          Allow bools in parameterized values (2021-12-12)

##  1.17.2          Fix hardcoded list of strictness choices on command line (2021-12-12)

#  1.18.0          Infer content-type and content-encoding from file_body key (2021-12-12)

#  1.19.0          Allow parametrizing more types of values (2022-01-09)

#  1.20.0          Add pytest_tavern_beta_after_every_test_run (2022-02-25)

#  1.21.0          Allow usage of pytest 7 (2022-04-17)

#  1.22.0          Allow usage of pyyaml 6 (2022-04-23)

##  1.22.1           Fix allure formatting stage name (2022-05-02)

#  1.23.0          Update pyjwt for CVE-2022-29217 (2022-06-05)

##  1.23.1          Fix docstring of fake pytest object to be a string (2022-06-05)

##  1.23.2          Fix newer versions of requests complaining about headers not being strings (2022-06-12)

##  1.23.3          Allow specifying 'unexpected' messages in MQTT to fail a test (2022-06-26)

##  1.23.4          Update stevedore version (2022-10-23)

##  1.23.5          Fix missing dependency in newer pytest versions (2022-11-07)

#  1.24.0          Fix using 'py' library (2022-11-08)


This locks pytest to <=7.2 to avoid having to fix imports every time a new version comes out.

##  1.24.1          Format variables in test error log before dumping as a YAML string (2022-11-22)

#  1.25.0          More changes to packaging (2022-12-13)


This is technically not a operational change but I'm adding a new tag so it can br reverted in future

##  1.25.1          Remove tbump from dependencies so it can actually be uploaded to pypi (2022-12-13)

##  1.25.2          Only patch pyyaml when a test is actually being loaded to avoid side effect from Tavern just being in the python path (2022-12-15)

#  2.0.0           2.0.0 release (2023-01-12)

##  2.0.1           Bump some dependency versions (2023-01-16)

##  2.0.2           Fix saving in MQTT (2023-02-08)

##  2.0.3           Add type annotations (internal change) (2023-02-10)

##  2.0.4           Fix using ext functions in MQTT publish (2023-02-16)

##  2.0.5           Attempt to fix deadlock in subscribe locks (2023-02-16)

##  2.0.6           Fix a few small MQTT issues (2023-03-13)

##  2.0.7           Lock pytest to <7.3 to fix issue with marks (2023-04-15)

#  2.1.0           Allow multi part file uploads with the same form field name (2023-06-04)

#  2.2.0           Allow wildcards in MQTT topics (2023-06-25)

##  2.2.1           Update some dependencies (2023-07-30)

#  2.3.0           Add 'finally' block (2023-08-05)

##  2.3.1           Fix error formatting when including files with curly braces (2023-09-18)

#  2.4.0           Allow using an ext function to create a URL (2023-09-18)

#  2.5.0           Tinctures: a utility for running things before/after stages, able to be specified at test or stage level. (2023-10-22)

#  2.6.0           fix verify_response_with with multiple MQTT responses (2023-11-18)

#  2.7.0           update minimum version of jsonschema (2023-12-26)

##  2.7.1           Fix jsonschema warnings (2023-12-26)

#  2.8.0           Initial gRPC support (2024-01-20)

#  2.9.0           Fix mqtt implementation checking for message publication correctly (2024-01-23)

##  2.9.1           internal cleanup (2024-01-27)

##  2.9.2           Fix saving in gRPC (2024-02-10)

##  2.9.3           Fix saving in gRPC without checking the response (2024-02-17)

#  2.10.0          Lock protobuf version to <5 (2024-03-27)

##  2.10.1          minor changes to fix tavern_flask plugin (2024-03-27)

##  2.10.2          Fix missing schema check for redirect query params (2024-04-13)

##  2.10.3          Allow using referenced 'finally' stages (2024-04-13)

#  2.11.0          Remove requirement for 'name' in variable files (2024-05-11)

#  2.12.0          Add dynamic skipping of stages based on simpleeval (2025-03-07)
