DEFAULT_VERSION = "3.8.3"

SDK_VERSIONS = {
    "3.8.3": "dfab5ec723c218082fe3d5d7ae17ecbdebffa9a1aea4d64aa3a2ecdd2e795864",
    "3.6.5": "f434053ba1b5c8a5cc597e966ead3c5143012af827fd3f0697d21450bb8d87a6",
}

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

def _remote_sdk(ctx, url, sha256):
    ctx.download(
        url = url,
        sha256 = sha256,
        output = "python_sdk.tar.xz",
    )

    res = ctx.execute(["tar", "-xf", "python_sdk.tar.xz", "--strip-components=1"])
    if res.return_code:
        fail("error extracting Python SDK:\n" + res.stdout + res.stderr)

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

    url = ctx.attr.url.format(version = version)

    _sdk_build_file(ctx)
    _remote_sdk(ctx, url, sha256)

python_download_sdk = repository_rule(
    _python_download_sdk_impl,
    attrs = {
        "version": attr.string(),
        "sha256": attr.string(),
        "url": attr.string(default = "https://www.python.org/ftp/python/{version}/Python-{version}.tar.xz"),
    },
)
