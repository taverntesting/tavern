DEFAULT_VERSION = "3.8.3"

SDK_VERSIONS = {
    "3.8.3": "dfab5ec723c218082fe3d5d7ae17ecbdebffa9a1aea4d64aa3a2ecdd2e795864",
    "3.6.5": "f434053ba1b5c8a5cc597e966ead3c5143012af827fd3f0697d21450bb8d87a6",
}

def _sdk_build_file(ctx):
    ctx.file("ROOT")
    ctx.template(
        "BUILD.bazel",
        Label("@tavern//support/private:BUILD.sdk.bzl"),
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

def _python_create_sdk_impl(ctx):
    runfiles = ctx.runfiles(
        files = ctx.files.deps,
    )

    outfile = ctx.actions.declare_file("out.txt")

    ctx.actions.run_shell(
        command = """
        ls
        exit 1
        """,
        inputs = ctx.files.deps,
        outputs = [outfile],
    )

    exec = ctx.actions.declare_file("exec.sh")

    ctx.actions.write(
        content =
            """
            fd
            echo $PYTHONPATH
            export PYTHONPATH=external/python_src/Lib/
            ./support/rules/python3
            exit 1
            """,
        is_executable = True,
        output = exec,
    )

    return [DefaultInfo(runfiles = runfiles, executable = exec)]

python_create_sdk = rule(
    _python_create_sdk_impl,
    executable = True,
    attrs = {
        "deps": attr.label_list(),
    },
)
