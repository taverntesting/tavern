# Controlling test flow

## Adding a delay between tests

Sometimes you might need to wait for some kind of uncontrollable external event
before moving on to the next stage of the test. To wait for a certain amount of time
before or after a test, the `delay_before` and `delay_after` keys can be used.
Say you have an asynchronous task running after sending a POST message with a
user id - an example of using this behaviour:

```yaml
---
test_name: Make sure asynchronous task updates database

stages:
  - name: Trigger task
    request:
      url: https://example.com/run_intensive_task_in_background
      method: POST
      json:
        user_id: 123
    # Server responds instantly...
    response:
      status_code: 200
    # ...but the task takes ~3 seconds to complete
    delay_after: 5

  - name: Check task has triggered
    request:
      url: https://example.com/check_task_triggered
      method: POST
      json:
        user_id: 123
    response:
      status_code: 200
      json:
        task: completed
```

Having `delay_before` in the second stage of the test is semantically identical
to having `delay_after` in the first stage of the test - feel free to use
whichever seems most appropriate.

A saved/config variable can be used by using a type token conversion, such as:

```yaml
stages:
  - name: Trigger task
    ...
    delay_after: !float "{sleep_time}"
```

## Retrying tests

If you are not sure how long the server might take to process a request, you can
also retry a stage a certain number of times using `max_retries`:

```yaml
---
test_name: Poll until server is ready

includes:
  - !include common.yaml

stages:
  - name: polling
    max_retries: 1
    request:
      url: "{host}/poll"
      method: GET
    response:
      status_code: 200
      json:
        status: ready
```

This example will perform a `GET` request against `/poll`, and if it does not
return the expected response, will try one more time, _immediately_. To wait
before retrying a request, combine `max_retries` with `delay_after`.

**NOTE**: You should think carefully about using retries when making a request
that will change some state on the server or else you may get nondeterministic
test results.

MQTT tests can be retried as well, but you should think whether this
is what you want - you could also try increasing the timeout on an expected MQTT
response to achieve something similar.

## Finalising stages

If you need a stage to run after a test runs, whether it passes or fails (for example, to log out of a service or
invalidate a short-lived auth token) you can use the `finally` block:

```yaml
---
test_name: Test finally block doing nothing

stages:
  - name: stage 1
    ...

  - name: stage 2
    ...

  - name: stage 3
    ...

finally:
  - name: clean up
    request:
      url: "{global_host}/cleanup"
      method: POST
```

The `finally` block accepts a list of stages which will always be run after the rest of the test finishes, whether it
passed or failed. Each stage in run in order - if one of the `finally` stages fails, the rest will not be run.

In the above example, if "stage 2" fails then the execution order would be:

- stage 1
- stage 2 (fails)
- clean up
