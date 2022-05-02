DEFAULT_VERSION = "1.37.2"

SDK_VERSIONS = {
    "1.37.2": {
        "darwin-amd64": "ba098e11b42b236c34aba112015b5661f3f70b44466f3fb27d83f93266193e4e",
        "darwin-arm64": "ff273fe06f132b253d74ef37c091c2b9eeb005b8634630226cf72949e5a03eb8",
        "linux-amd64": "5028755d1e8e5bd87b4185785b9c490002862bf62d75f76f45c91ff6fea0a0ab",
        "linux-arm64": "e86c1e0d053bcfea10d1853eb31f39a796cade685dd74bf75a8803be8c044189",
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
