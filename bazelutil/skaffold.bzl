DEFAULT_VERSION = "1.38.0"

SDK_VERSIONS = {
    "1.38.0": {
        "darwin-amd64": "872897d78a17812913cd6e930c5d1c94f7c862381db820815c4bffc637c28b88",
        "darwin-arm64": "e47329560a557f0f01d7902eae01ab8d40210b40644758f957f071ab8df2ac44",
        "linux-amd64": "3c347c9478880f22ebf95807c13371844769c625cf3ea9c987cd85859067503c",
        "linux-arm64": "41c6385443787f864eaa448b985479115aa917b045245efb38d15d4b2dc5fed3",
    },
}

def _get_skaffold(ctx):
    if ctx.attr.version:
        version = ctx.attr.version

        if not ctx.attr.sha256:
            fail("sha256 must be specified if using custom version")
        sha256 = ctx.attr.sha256
    else:
        if ctx.attr.sha256:
            fail("sha256 ignored when no version is passed")

        version = DEFAULT_VERSION
        sha256 = SDK_VERSIONS[version]["{name}-{arch}".format(name = ctx.os.name, arch = ctx.os.arch)]

    url = ctx.attr.url.format(version = version, name = ctx.os.name, arch = ctx.os.arch)

    ctx.download(
        url = url,
        executable = True,
        sha256 = sha256,
        output = "skaffold",
    )

    ctx.file(
        "BUILD.bazel",
        """exports_files(["skaffold"])""",
    )
    ctx.file("WORKSPACE", "workspace(name = \"{name}\")".format(name = ctx.name))

get_skaffold = repository_rule(
    implementation = _get_skaffold,
    attrs = {
        "version": attr.string(),
        "sha256": attr.string(),
        "url": attr.string(default = "https://github.com/GoogleContainerTools/skaffold/releases/download/v{version}/skaffold-{name}-{arch}"),
    },
)
