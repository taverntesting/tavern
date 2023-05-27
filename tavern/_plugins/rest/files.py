import dataclasses
import logging
import mimetypes
import os
from contextlib import ExitStack
from typing import Optional, Union

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Filespec:
    """A description of a file for a file upload, possibly as part of a multi part upload"""

    path: str
    content_type: Optional[str] = None
    content_encoding: Optional[str] = None
    group_name: Optional[str] = None


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
            filespec.get("group_name"),
        )
    else:
        # Could remove, also done in schema check
        raise exceptions.BadSchemaError(
            "File specification must be a path or a dictionary"
        )


def guess_filespec(
    filespec: Union[str, dict], stack: ExitStack, test_block_config: TestConfig
):
    """tries to guess the content type and encoding from a file.

    Args:
        test_block_config: config for test/stage
        stack: exit stack to add open files context to
        filespec: a string path to a file or a dictionary of the file path, content type, and encoding.

    Returns:
        A tuple of either length 2 (filename and file object), 3 (as before, with content type), or 4 (as before, with with content encoding)

    Notes:
        If a 4-tuple is returned, the last element is a dictionary of headers to send to requests, _not_ the raw encoding value.
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

    return file_spec


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

    files_to_send = {}

    for key, filespec in request_args.get("files", {}).items():
        file_spec = guess_filespec(filespec, stack, test_block_config)

        files_to_send[key] = tuple(file_spec)

    if files_to_send:
        return {"files": files_to_send}
    else:
        return {}
