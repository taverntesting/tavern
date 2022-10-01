FileCountInfo = provider(
    fields = {
        "lint_out": "lint output",
    },
)

def _file_count_aspect_impl(target, ctx):
    if hasattr(ctx.rule.attr, "deps"):
        transitive = [dep[FileCountInfo].lint_out for dep in ctx.rule.attr.deps]
    else:
        transitive = []

    if str(target.label).startswith("//") and ctx.rule.kind.startswith("py_"):
        # Make sure the rule has a srcs attribute.
        if hasattr(ctx.rule.attr, "srcs"):
            srcs = ctx.rule.attr.srcs
            srcs = [s.files for s in srcs]

            srcs = [s.to_list() for s in srcs]
            srcs = [i[0] for i in srcs]

            src_paths = [i.path for i in srcs]

            flake8_out = ctx.actions.declare_file(ctx.rule.attr.name + ".flake8")
            ctx.actions.run(
                outputs = [flake8_out],
                inputs = srcs + [ctx.file._flake8_config],
                executable = ctx.files._linter[1],
                arguments = ["--tee", "--config", ctx.file._flake8_config.path, "--output-file", flake8_out.path] + src_paths,
                mnemonic = "Flake8",
            )

            return [
                FileCountInfo(
                    lint_out = depset([flake8_out], transitive = transitive),
                ),
            ]

    return [
        FileCountInfo(
            lint_out = depset([], transitive = transitive),
        ),
    ]

file_count_aspect = aspect(
    implementation = _file_count_aspect_impl,
    attr_aspects = ["deps"],
    attrs = {
        "_linter": attr.label(
            allow_files = True,
            default = "@tavern_pip_flake8//:rules_python_wheel_entry_point_flake8",
        ),
        "_flake8_config": attr.label(
            allow_single_file = True,
            default = "//:.flake8",
        ),
    },
)

def _file_count_rule_impl(ctx):
    all_lint_out = []
    for dep in ctx.attr.deps:
        all_lint_out += dep[FileCountInfo].lint_out.to_list()

    report_total = ctx.actions.declare_file(ctx.attr.name + ".report_total")

    ctx.actions.run_shell(
        outputs = [report_total],
        inputs = all_lint_out,
        command = "cat {0} | tee {1}".format(
            " ".join([i.path for i in all_lint_out]),
            report_total.path,
        ),
    )

    return [
        OutputGroupInfo(
            report = depset([report_total]),
        ),
    ]

file_count_rule = rule(
    implementation = _file_count_rule_impl,
    attrs = {
        "deps": attr.label_list(aspects = [file_count_aspect]),
        "report_total": attr.output(),
    },
)
