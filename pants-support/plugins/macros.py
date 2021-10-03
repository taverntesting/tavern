lint_ver = "3.9"


def test_lib(lower, upper, **kwargs):
    skips = ["flake8", "pylint", "mypy"]
    if lower != lint_ver:
        skips += ["black", "docformatter", "isort"]
    for s in skips:
        kwargs[f"skip_{s}"] = True

    python_tests(
        name=f"test_{lower}",
        sources=[
            "unit/test_*.py",
        ],
        interpreter_constraints=[f"CPython>={lower},<{upper}"],
        **kwargs
    )


def python3_multitests(**kwargs):
    kwargs.pop("interpreter_constraints", None)

    test_lib("3.7", "3.8", **kwargs)
    test_lib("3.8", "3.9", **kwargs)
    test_lib("3.9", "3.10", **kwargs)
