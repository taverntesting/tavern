import functools
import hashlib
import importlib.util
import logging
import os
import string
import subprocess
import sys
import tempfile
from distutils.spawn import find_executable
from importlib.machinery import ModuleSpec

from tavern._core import exceptions

logger: logging.Logger = logging.getLogger(__name__)


@functools.lru_cache
def find_protoc() -> str:
    # Find the Protocol Compiler.
    if "PROTOC" in os.environ and os.path.exists(os.environ["PROTOC"]):
        return os.environ["PROTOC"]

    if protoc := find_executable("protoc"):
        return protoc

    raise exceptions.ProtoCompilerException(
        "Wanted to dynamically compile a proto source, but could not find protoc"
    )


@functools.lru_cache
def _generate_proto_import(source: str) -> None:
    """Invokes the Protocol Compiler to generate a _pb2.py from the given
    .proto file.  Does nothing if the output already exists and is newer than
    the input.
    """

    if not os.path.exists(source):
        raise exceptions.ProtoCompilerException(f"Can't find required file: {source}")

    logger.info("Generating protos from %s...", source)

    # If its a dir, compile them all
    if not os.path.isdir(source):
        if not source.endswith(".proto"):
            raise exceptions.ProtoCompilerException(
                f"invalid proto source file {source}"
            )
        protos = [source]
        include_path = os.path.dirname(source)
    else:
        protos = [
            os.path.join(source, child)
            for child in os.listdir(source)
            if (not os.path.isdir(child)) and child.endswith(".proto")
        ]
        include_path = source

    if not protos:
        raise exceptions.ProtoCompilerException(
            f"No protos defined in {os.path.abspath(source)}"
        )

    for p in protos:
        if not os.path.exists(p):
            raise exceptions.ProtoCompilerException(f"{p} does not exist")

    def sanitise(s):
        """Do basic sanitisation for creating a temporary directory based on
        the name of the input proto file"""
        return "".join(c for c in s if c in string.ascii_letters)

    # Create a temporary directory to put the generated protobuf files in
    output = os.path.join(
        tempfile.gettempdir(),
        "tavern_proto",
        sanitise(protos[0]),
        hashlib.new("sha3_224", "".join(protos).encode("utf8")).hexdigest(),
    )

    if not os.path.exists(output):
        os.makedirs(output)

    protoc = find_protoc()

    protoc_command = [protoc, "-I" + include_path, "--python_out=" + output]
    protoc_command.extend(protos)

    call = subprocess.run(protoc_command, capture_output=True, check=False)  # noqa
    if call.returncode != 0:
        logger.error(f"Error calling '{protoc_command}'")
        raise exceptions.ProtoCompilerException(call.stderr.decode("utf8"))

    logger.info(f"Generated module from protos: {protos}")

    # Invalidate caches so the module can be loaded
    sys.path.append(output)
    importlib.invalidate_caches()
    _import_grpc_module(output)


def _import_grpc_module(python_module_name: str) -> None:
    """takes an expected python module name and tries to import the relevant
    file, adding service to the symbol database.
    """

    logger.debug("attempting to import %s", python_module_name)

    if python_module_name.endswith(".py"):
        raise exceptions.GRPCServiceException(
            f"grpc module definitions should not end with .py, but got {python_module_name}"
        )

    if python_module_name.startswith("."):
        raise exceptions.GRPCServiceException(
            f"relative imports for Python grpc modules not allowed (got {python_module_name})"
        )

    import_specs: list[ModuleSpec] = []

    # Check if its already on the python path
    if (spec := importlib.util.find_spec(python_module_name)) is not None:
        logger.debug(f"{python_module_name} on sys path already")
        import_specs.append(spec)

    # See if the file exists
    module_path = python_module_name.replace(".", "/") + ".py"
    if os.path.exists(module_path):
        logger.debug(f"{python_module_name} found in file")
        if (
            spec := importlib.util.spec_from_file_location(
                python_module_name, module_path
            )
        ) is not None:
            import_specs.append(spec)

    # If its a dir then load files in the dir instead
    if os.path.isdir(python_module_name):
        for s in os.listdir(python_module_name):
            s = os.path.join(python_module_name, s)
            if s.endswith(".py"):
                logger.debug(f"found py file {s}")
                # Guess a package name
                if (
                    spec := importlib.util.spec_from_file_location(s[:-3], s)
                ) is not None:
                    import_specs.append(spec)

    if not import_specs:
        raise exceptions.GRPCServiceException(
            f"could not determine how to import {python_module_name}"
        )

    # Actually import them to register them in the symbol db
    for spec in import_specs:
        mod = importlib.util.module_from_spec(spec)
        logger.debug(f"loading from {spec.name}")
        if spec.loader:
            spec.loader.exec_module(mod)
