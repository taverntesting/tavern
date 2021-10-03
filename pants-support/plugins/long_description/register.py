import os.path

from pants.backend.python.goals.setup_py import SetupKwargs
from pants.backend.python.goals.setup_py import SetupKwargsRequest
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
from pants.engine.rules import Get, rule
from pants.engine.rules import collect_rules
from pants.engine.target import Target
from pants.engine.unions import UnionRule


class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True


@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    async def get_file_content(original_kwargs, request, filename):
        file_relpath = original_kwargs.pop(filename, None)
        if not file_relpath:
            raise ValueError(
                f"The python_distribution target {request.target.address} did not include "
                f"`{filename}` in its setup_py's kwargs. Our plugin requires this! "
                "Please set to a path relative to the BUILD file, e.g. `ABOUT.md`."
            )
        build_file_path = request.target.address.spec_path
        file_path = os.path.join(build_file_path, file_relpath)
        digest_contents = await Get(
            DigestContents,
            PathGlobs(
                [file_path],
                description_of_origin=f"the '{filename}' kwarg in {request.target.address}",
                glob_match_error_behavior=GlobMatchErrorBehavior.error,
            ),
        )
        return digest_contents[0].content.decode()

    original_kwargs = request.explicit_kwargs.copy()
    description_content = await get_file_content(original_kwargs, request, "long_description_file")
    return SetupKwargs(
        {
            **original_kwargs,
            "long_description": description_content,
        },
        address=request.target.address
    )


def rules():
    return [
        *collect_rules(),
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]
