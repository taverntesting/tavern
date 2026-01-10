import dataclasses
import logging
import mimetypes
import os
from contextlib import ExitStack
from io import IOBase
from typing import Any, NamedTuple, Optional, Union

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Filespec:
    """A description of a file for a file upload, possibly as part of a multi part upload"""

    path: str
    content_type: str | None = None
    content_encoding: str | None = None
    form_field_name: str | None = None


def _parse_filespec(filespec: str | dict) -> _Filespec:
    """
    Get configuration for uploading file

    Args:
        filespec: Can either be one of
            - A path to a file
            - A dict containing 'long' format, possibly including content type/encoding and the
                multipart 'name'

    Returns:
        The parsed file spec

    Raises:
        exceptions.BadSchemaError: If the file spec was invalid
    """
    if isinstance(filespec, str):
        return _Filespec(filespec)
    elif isinstance(filespec, dict):
        try:
            # The one required key
            path = filespec["file_path"]
        except KeyError as e:
            raise exceptions.BadSchemaError(
                "File spec dict did not contain the required 'file_path' key"
            ) from e

        return _Filespec(
            path,
            filespec.get("content_type"),
            filespec.get("content_encoding"),
            filespec.get("form_field_name"),
        )
    else:
        # Could remove, also done in schema check
        raise exceptions.BadSchemaError(
            f"File specification must be a path or a dictionary but got {type(filespec)}"
        )


class FileSendSpec(NamedTuple):
    """A description of a file to send as part of a multipart/form-data upload to requests"""

    filename: str
    file_obj: IOBase
    content_type: Optional[str] = None
    content_encoding: Optional[str | dict] = None


def guess_filespec(
    filespec: Union[str, dict], stack: ExitStack, test_block_config: TestConfig
) -> tuple[FileSendSpec, Optional[str], str]:
    """tries to guess the content type and encoding from a file.

    Args:
        filespec: a string path to a file or a dictionary of the file path, content type, and encoding.
        test_block_config: config for test/stage
        stack: exit stack to add open files context to

    Returns:
        A tuple of either length 2 (filename and file object), 3 (as before, with content type),
            or 4 (as before, with with content encoding). If a group name for the multipart upload
            was specified, this is also returned.

    Notes:
        If a 4-tuple is returned, the last element is a dictionary of headers to send to requests,
            _not_ the raw encoding value.
    """
    if not mimetypes.inited:
        mimetypes.init()

    parsed = _parse_filespec(filespec)

    resolved_file_path = format_keys(parsed.path, test_block_config.variables)
    filename = os.path.basename(resolved_file_path)

    # a 2-tuple ('filename', fileobj)
    file_spec = [
        filename,
        stack.enter_context(open(resolved_file_path, "rb")),
    ]

    # Try to guess as well, but don't override what the user specified
    guessed_content_type, guessed_encoding = mimetypes.guess_type(resolved_file_path)
    content_type = parsed.content_type or guessed_content_type
    encoding = parsed.content_encoding or guessed_encoding

    # If it doesn't have a mimetype, or can't guess it, don't
    # send the content type for the file
    if content_type:
        # a 3-tuple ('filename', fileobj, 'content_type')
        logger.debug("content_type for '%s' = '%s'", filename, content_type)
        file_spec.append(content_type)
        if encoding:
            # or a 4-tuple ('filename', fileobj, 'content_type', custom_headers)
            logger.debug("encoding for '%s' = '%s'", filename, encoding)
            # encoding is None for no encoding or the name of the
            # program used to encode (e.g. compress or gzip). The
            # encoding is suitable for use as a Content-Encoding header.
            file_spec.append({"Content-Encoding": encoding})

    return FileSendSpec(*file_spec), parsed.form_field_name, resolved_file_path  # type: ignore


def _parse_file_mapping(file_args, stack, test_block_config) -> dict[str, FileSendSpec]:
    """Parses a simple mapping of uploads where each key is mapped to one form field name which has one file"""
    files_to_send = {}
    for key, filespec in file_args.items():
        file_spec, form_field_name, _ = guess_filespec(
            filespec, stack, test_block_config
        )

        # If it's a dict then the key is used as the name, at least to maintain backwards compatability
        if form_field_name:
            logger.warning(
                f"Specified 'form_field_name' as '{form_field_name}' in file spec, but the file name was inferred to be '{key}' from the mapping - the form_field_name will be ignored"
            )

        files_to_send[key] = file_spec

    return files_to_send


def _parse_file_list(
    file_args: list,
    stack: ExitStack,
    test_block_config: TestConfig,
) -> list[tuple[str, FileSendSpec]]:
    """Parses a case where there may be multiple files uploaded as part of one form field"""
    files_to_send: list[Any] = []
    for filespec in file_args:
        file_spec, form_field_name, _ = guess_filespec(
            filespec, stack, test_block_config
        )

        if not form_field_name:
            raise exceptions.BadSchemaError(
                "If specifying a list of files to upload for a multi part upload, the 'form_field_name' key must also be specified for each file to upload"
            )

        files_to_send.append(
            (
                form_field_name,
                file_spec,
            )
        )

    return files_to_send
