workspace(name = "tavern")

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

http_archive(
    name = "rules_python",
    sha256 = "b5668cde8bb6e3515057ef465a35ad712214962f0b3a314e551204266c7be90c",
    strip_prefix = "rules_python-0.0.2",
    url = "https://github.com/bazelbuild/rules_python/releases/download/0.0.2/rules_python-0.0.2.tar.gz",
)

load("@rules_python//python:pip.bzl", "pip3_import", "pip_repositories")

pip_repositories()

pip3_import(
    name = "tavern_deps",
    requirements = "//:requirements.txt",
)

load("@tavern_deps//:requirements.bzl", "pip_install")

pip_install()

http_archive(
    name = "com_github_ali5h_rules_pip",
    sha256 = "630a7cab43a87927353efca116d20201df88fb443962bf01c7383245c7f3a623",
    strip_prefix = "rules_pip-3.0.0",
    urls = ["https://github.com/ali5h/rules_pip/archive/3.0.0.tar.gz"],
)

load("@tavern//support/rules:python_sdk.bzl", "python_download_sdk")

python_download_sdk(name = "python_interpreter")
