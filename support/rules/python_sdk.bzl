PLATFORMS = ["linux_amd64"]
#    PLATFORMS = ["linux_amd64", "darwin_amd64"]

DEFAULT_VERSION = "3.8.3"

SDK_VERSIONS = {
    "3.8.3": "dfab5ec723c218082fe3d5d7ae17ecbdebffa9a1aea4d64aa3a2ecdd2e795864",
}

def _register_toolchains(repo):
    labels = [
        "@{}//:{}".format(repo, name)
        for name in generate_toolchain_names()
    ]
    native.register_toolchains(*labels)

def generate_toolchain_names():
    # keep in sync with declare_toolchains
    return ["python_bin_" + p for p in PLATFORMS]

def _sdk_build_file(ctx):
    ctx.file("ROOT")
    ctx.template(
        "BUILD.bazel",
        Label("@tavern//support/private:BUILD.sdk.bazel"),
        executable = False,
        substitutions = {
            "{arch}": "linux_amd64",
        },
    )

def _remote_sdk(ctx, url, strip_prefix, sha256):
    if strip_prefix != "python":
        fail("strip_prefix not supported")

    ctx.download(
        url = url,
        sha256 = sha256,
        output = "python_sdk.tar.xz",
    )

    res = ctx.execute(["tar", "-xf", "python_sdk.tar.xz", "--strip-components=1"])
    if res.return_code:
        fail("error extracting Go SDK:\n" + res.stdout + res.stderr)

    ctx.execute(["rm", "python_sdk.tar.xz"])

def _python_download_sdk_impl(ctx):
    if ctx.attr.version:
        if not (ctx.attr.version.startswith("2") or ctx.attr.version.startswith("3")):
            fail("mangled Python version: {}".format(ctx.attr.version))

        version = ctx.attr.version

        if not ctx.attr.sha256:
            if version not in SDK_VERSIONS:
                fail("hash must be specified if using custom version")
            else:
                sha256 = SDK_VERSIONS[version]
        else:
            sha256 = ctx.attr.sha256
    else:
        version = DEFAULT_VERSION
        sha256 = SDK_VERSIONS[version]

    if ctx.os.name == "linux":
        _py_configure = """
        ./configure --prefix=$(pwd)/bazel_install
        """
    elif ctx.os.name == "mac os x":
        _py_configure = """
        ./configure --prefix=$(pwd)/bazel_install --with-openssl=$(brew --prefix openssl)
        """
    else:
        fail("unsupported")

    url = ctx.attr.url.format(version = version)

    _sdk_build_file(ctx)
    _remote_sdk(ctx, url, ctx.attr.strip_prefix, sha256)

    patch_cmds = [
        "mkdir $(pwd)/bazel_install",
        _py_configure,
        "make -j 10",
        "make -j 10 install",
        "ln -s bazel_install/bin/python3 python_bin",
    ]

    for cmd in patch_cmds:
        ctx.execute(cmd.split(" "))

def python_download_sdk(name, **kwargs):
    _python_download_sdk(name = name, **kwargs)
    _register_toolchains(name)

_python_download_sdk = repository_rule(
    _python_download_sdk_impl,
    attrs = {
        "version": attr.string(),
        "sha256": attr.string(),
        "url": attr.string(default = "https://www.python.org/ftp/python/{version}/Python-{version}.tar.xz"),
        "strip_prefix": attr.string(default = "python"),
    },
)
