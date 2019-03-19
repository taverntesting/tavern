from tavern.core import run


class TestBasicRun:
    def test_run(self):
        run("")

    def test_run_with_empty_cfg(self):
        run("", {})

    def test_run_with_cfg(self):
        run("", {"a": 2})
