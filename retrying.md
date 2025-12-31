# The problem

Currently tavern allows oyu to specify a request and the expected response.

People want to be able to say "if this response is received, then actually try the request again until the other
response is received".

For example from a user:

>     /status endpoint that returns the status of the job, e.g., QUEUED, IN_PROGRESS, SUCCESS and FAILED
>  I'd like to express a test that keeps re-trying the /status endpoint until the status is either SUCCESS or FAILED.
> This could indeed be achieved with the retry functionality, but that would result in a rather flaky test as the
> duration
> of the task varies heavily.
> the difference here is that my long running task can possibly take an hour to complete, while failure along the way is
> very likely. So it would be relevant to specify additional stop (and failure) conditions.

This might look something like

```yaml
stages:
  - name: get status
    request:
      url: "{host}/status"
    retry_if:
      - response:
          status_code: 200
          json:
            status: QUEUED
      - response:
          status_code: 200
          json:
            status: IN_PROGRESS
    response:
      status_code: 200
      json:
        status: SUCCESS
```

The user wants to make a request to the status endpoint, if it returns QUEUED or IN_PROGRESS then retry the request
again after some backoff, until it returns SUCCESS. If it returns FAILED then fail the test, because this is not
covered.

There should also be a way to specify the number of times to retry, how long to backoff, total time to wait for the
response, etc.

Files to update:

- tavern/_core/schema/tests.jsonschema.yaml for the schema
- tavern/_core/run.py or maybe tavern/_core/testhelpers.py for the retry logic
- The README.md explaining how to use it
- tavern/_core/plugins.py to handle response validation, if needed