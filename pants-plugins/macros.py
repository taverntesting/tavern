def python3_multitests(**kwargs):
    kwargs.pop("interpreter_constraints", None)

    python_tests(
        name=f"tests_py3.7",
        interpreter_constraints={"CPython": ">=3.7,<3.8"},
        **kwargs,
    )

    python_tests(
        name=f"tests_py3.8",
        interpreter_constraints={"CPython": ">=3.8,<3.9"},
        **kwargs,
    )

    python_tests(
        name=f"tests_py3.9",
        interpreter_constraints={"CPython": ">=3.9,<3.10"},
        **kwargs,
    )
