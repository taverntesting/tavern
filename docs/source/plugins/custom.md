# Custom backends

Though tavern supports a few backends out of the box, you may want to extend it to support your own.
This can be done by creating a new plugin that implements the necessary functionality and registers it with tavern.

First, write your backend and set up the request, response, etc as according to the [standard plugin system](../plugins.md).
Note the standard restrictions - there can only be one 'request' per stage.

## Entry Point Configuration

In your project's `pyproject.toml`, configure the plugin entry point:

```toml
[project.entry-points.tavern_your_backend_name]
my_implementation = 'your.package.path:your_backend_module'
```

Then when running tests, specify the extra backend:

```bash
pytest --tavern-extra-backends=your_backend_name
# Or, to specify an implementation to override the project entrypoint:
pytest --tavern-extra-backends=your_backend_name=my_other_implementation
```

Or the equivalent in pyproject.toml or pytest.ini. Note:

- The entry point name should start with `tavern_`.
- The key of the entrypoint is just a name of the implementation and can be anything.
- The `--tavern-extra-backends` flag should *not* be prefixed with `tavern_`.
- If Tavern detects multiple entrypoints for a backend, it will raise an error. In this case, you must use the second
  form to specify which implementation of the backend to use. This is similar to the build-in `--tavern-http-backend`
  flag.

This is because Tavern by default only tries to load "grpc", "http" and "mqtt" backends. The flag registers the custom
backend with Tavern, which can then tell [stevedore](https://github.com/openstack/stevedore) to load the plugin from the
entrypoint.

## Future work

- Currently only the builtin tavern backends can have multiple responses to a request.