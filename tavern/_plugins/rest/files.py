import dataclasses
import logging
import mimetypes
import os
from contextlib import ExitStack
from typing import Any, Optional, Union

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Filespec:
    """A description of a file for a file upload, possibly as part of a multi part upload"""

    path: str
    content_type: Optional[str] = None
    content_encoding: Optional[str] = None
    form_field_name: Optional[str] = None


def _parse_filespec(filespec: Union[str, dict]) -> _Filespec:
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
            "File specification must be a path or a dictionary"
        )


def guess_filespec(
    filespec: Union[str, dict], stack: ExitStack, test_block_config: TestConfig
) -> tuple[list, Optional[str]]:
    """tries to guess the content type and encoding from a file.

    Args:
        test_block_config: config for test/stage
        stack: exit stack to add open files context to
        filespec: a string path to a file or a dictionary of the file path, content type, and encoding.

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

    filepath = format_keys(parsed.path, test_block_config.variables)
    filename = os.path.basename(filepath)

    # a 2-tuple ('filename', fileobj)
    file_spec = [
        filename,
        stack.enter_context(open(filepath, "rb")),
    ]

    # Try to guess as well, but don't override what the user specified
    guessed_content_type, guessed_encoding = mimetypes.guess_type(filepath)
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

    return file_spec, parsed.form_field_name


def _parse_file_mapping(file_args, stack, test_block_config) -> dict:
    """Parses a simple mapping of uploads where each key is mapped to one form field name which has one file"""
    files_to_send = {}
    for key, filespec in file_args.items():
        file_spec, form_field_name = guess_filespec(filespec, stack, test_block_config)

        # If it's a dict then the key is used as the name, at least to maintain backwards compatability
        if form_field_name:
            logger.warning(
                f"Specified 'form_field_name' as '{form_field_name}' in file spec, but the file name was inferred to be '{key}' from the mapping - the form_field_name will be ignored"
            )

        files_to_send[key] = tuple(file_spec)
    return files_to_send


def _parse_file_list(file_args, stack, test_block_config) -> list:
    """Parses a case where there may be multiple files uploaded as part of one form field"""
    files_to_send: list[Any] = []
    for filespec in file_args:
        file_spec, form_field_name = guess_filespec(filespec, stack, test_block_config)

        if not form_field_name:
            raise exceptions.BadSchemaError(
                "If specifying a list of files to upload for a multi part upload, the 'form_field_name' key must also be specified for each file to upload"
            )

        files_to_send.append(
            (
                form_field_name,
                tuple(file_spec),
            )
        )

    return files_to_send


def get_file_arguments(
    request_args: dict, stack: ExitStack, test_block_config: TestConfig
) -> dict:
    """Get correct arguments for anything that should be passed as a file to
    requests

    Args:
        request_args: args passed to requests
        test_block_config: config for test
        stack: context stack to add file objects to so they're
            closed correctly after use

    Returns:
        mapping of 'files' block to pass directly to requests
    """

    files_to_send: Optional[Union[dict, list]] = None

    file_args = request_args.get("files")

    if isinstance(file_args, dict):
        files_to_send = _parse_file_mapping(file_args, stack, test_block_config)
    elif isinstance(file_args, list):
        files_to_send = _parse_file_list(file_args, stack, test_block_config)
    elif file_args is not None:
        raise exceptions.BadSchemaError(
            f"'files' key in a HTTP request can only be a dict or a list but was {type(file_args)}"
        )

    if files_to_send:
        return {"files": files_to_send}
    else:
        return {}
