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
            report_out = ctx.actions.declare_file("lint_output_" + ctx.rule.attr.name)
            srcs = ctx.rule.attr.srcs
            srcs = [s.files for s in srcs]

            srcs = [s.to_list() for s in srcs]
            srcs = [i[0] for i in srcs]

            src_paths = [i.path for i in srcs]

            location = ctx.expand_location("$(locations @tavern_pip_flake8//:rules_python_wheel_entry_point_flake8)", [ctx.attr._linter])
            location = location.split(" ")[0]

            ctx.actions.run_shell(
                outputs = [report_out],
                inputs = srcs + [ctx.file._flake8_config],
                tools = ctx.files._linter,
                command = """
                {0} {1} --config {2} --exit-zero | tee {3}
                """.format(location, " ".join(src_paths), ctx.file._flake8_config.path, report_out.path),
            )

            report_out = depset([report_out], transitive = transitive)

            return [
                OutputGroupInfo(
                    report = report_out,
                ),
                FileCountInfo(
                    lint_out = report_out,
                ),
            ]

    return [FileCountInfo(
        lint_out = depset([], transitive = transitive),
    )]

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
        DefaultInfo(
            files = depset([report_total]),
        ),
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
