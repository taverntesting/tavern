from functools import partial


class partialmethod(partial):
    """Like Python 3's partialmethod but backported for Python 2
    """
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return partial(self.func, instance, *(self.args or ()), **(self.keywords or {}))


def indent(text, prefix):
    """ String indentation """
    try:
        from textwrap import indent as _indent
    except ImportError:  # undefined function (wasn't added until Python 3.3)
        def _indent(text, prefix): # Currently not supporting predicate arg
            return ''.join(prefix+line for line in text.splitlines(True))

    return _indent(text, prefix)
