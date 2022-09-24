FileCountInfo = provider(
    fields = {
        "lint_out": "lint output",
    },
)

def _file_count_aspect_impl(target, ctx):
    if str(target.label).startswith("//") and ctx.rule.kind.startswith("py_"):
        # Make sure the rule has a srcs attribute.
        if hasattr(ctx.rule.attr, "srcs"):
            print("Doing " + str(target.label))
            report_out = ctx.actions.declare_file("lint_output_" + ctx.rule.attr.name)
            srcs = ctx.rule.attr.srcs
            srcs = [s.files for s in srcs]

            srcs = [s.to_list() for s in srcs]
            srcs = [i[0] for i in srcs]

            ctx.actions.run_shell(
                outputs = [report_out],
                inputs = srcs,
                command = "exit 1",
            )

            report_out = depset([report_out], transitive = [dep[FileCountInfo].lint_out for dep in ctx.rule.attr.deps])

            return [
                OutputGroupInfo(
                    report = report_out,
                ),
                FileCountInfo(
                    lint_out = report_out,
                ),
            ]

    return [FileCountInfo(
        lint_out = depset([], transitive = [dep[FileCountInfo].lint_out for dep in ctx.rule.attr.deps]),
    )]

file_count_aspect = aspect(
    implementation = _file_count_aspect_impl,
    attr_aspects = ["deps"],
    attrs = {
        "_linter": attr.label(default = "@tavern_pip_flake8//:rules_python_wheel_entry_point_flake8"),
    },
)

def _file_count_rule_impl(ctx):
    for dep in ctx.attr.deps:
        print(dep[FileCountInfo].lint_out.to_list())

        run_script = ctx.actions.declare_file(ctx.label.name)
        ctx.actions.write(
            content = "echo " + str(dep[FileCountInfo].lint_out.to_list()),
            output = run_script,
            is_executable = True,
        )

        return [DefaultInfo(executable = run_script)]

file_count_rule = rule(
    executable = True,
    implementation = _file_count_rule_impl,
    attrs = {
        "deps": attr.label_list(aspects = [file_count_aspect]),
    },
)
