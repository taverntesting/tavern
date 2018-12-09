import time
from locust import Locust, events
from tavern.core import run


class TavernClient(object):
    def __init__(self, *args, **kwargs):
        # super(TavernClient, self).__init__(*args, **kwargs)
        pass

    def run_tavern_tests(
        self,
        names_contain=None,
        mark_specifier=None,
        filename=None,
        extra_pytest_args=None,
    ):
        if not (names_contain or mark_specifier or filename):
            raise RuntimeError(
                "Must specify one of names_contain, mark_specifier, or filename"
            )

        joined_args = ["--disable-pytest-warnings", "--no-cov", "-qqqqqqqq"]

        name = "tavern:"

        if filename:
            joined_args += [filename]
            name += ",f:{}".format(filename)
        if mark_specifier:
            joined_args += ["-m", mark_specifier]
            name += ",m:{}".format(",".join(mark_specifier).replace(" ", ""))
        if names_contain:
            joined_args += ["-k", names_contain]
            name += ",k:{}".format(",".join(names_contain).replace(" ", ""))

        start_time = time.time()
        try:
            run(filename, pytest_args=joined_args)
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request_failure.fire(
                request_type="tavern", name=name, response_time=total_time, exception=e
            )
        else:
            total_time = int((time.time() - start_time) * 1000)
            events.request_success.fire(
                request_type="tavern",
                name=name,
                response_time=total_time,
                response_length=0,
            )


class TavernLocust(Locust):
    def __init__(self, *args, **kwargs):
        super(TavernLocust, self).__init__(*args, **kwargs)
        self.client = TavernClient(self.host)
