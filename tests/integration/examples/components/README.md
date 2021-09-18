# Load external components (stage) example

In this example we need to authenticate for every request to the server. Every
test file needs to do this. To avoid duplication, we do the following:

- Have server with /ping and /hello endpoints, both requiring JWT to complete
  the request.
- Create components/auth_stage.yaml - this defines a stage that logs in *and*
  saves the token for subsequent stages.
- Create two tests, one for each distinct endpoint. Each test will *include* the
  external components (authentication/login stage), and then execute the stage
  where we need it.


This allows stages to be defined outside of the context of a test spec, and be
included in many test specs, in different files.
