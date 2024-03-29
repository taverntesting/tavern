"""Contains types useful for annotating things in Tavern to avoid copy/pasting everywhere"""

import typing

# Anything json might be decoded to
Json = typing.Union[typing.Mapping, typing.Sequence, str, int, float, None]
