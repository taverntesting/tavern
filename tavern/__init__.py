"""Tavern pytest plugin.

Stop pytest warning about module already imported: PYTEST_DONT_REWRITE
"""

import importlib.metadata

__version__ = importlib.metadata.version("tavern")
