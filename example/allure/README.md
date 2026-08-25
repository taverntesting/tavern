# Allure example

A couple of tests, one of them parametrized, run against the server from
[the http example](../http) and reported with
[allure](https://allurereport.org/).

The parametrized test is the interesting one: Tavern generates a separate test item
per combination, so each of them should appear as its own test case in the report
rather than overwriting each other (see
[#1078](https://github.com/taverntesting/tavern/issues/1078)).

## Running it

```bash
docker compose up --build -d
uv run pytest --alluredir=allure-results
docker compose run --rm allure generate /allure-results --clean --single-file -o /allure-report
docker compose down -v
```

This is what `tox -c tox-integration.ini -e py3-allure` does from the root of the repo.

`--single-file` writes the whole report to `allure-report/index.html`, which can be
opened directly in a browser - a normal multi-file allure report has to be served over
HTTP. The report is written from inside the container, so the files in `allure-report`
and `allure-results` are owned by root.
