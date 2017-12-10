
""" Python 2 format_map string compatibility. Monkey patches the
format_map method on to the build in string type

From https://gist.github.com/zed/1384338
"""
try: 
    ''.format_map({})
except AttributeError: # Python < 3.2
    import string
    def format_map(format_string, mapping, _format=string.Formatter().vformat):
        return _format(format_string, None, mapping)
    del string

    #XXX works on CPython 2.6
    # http://stackoverflow.com/questions/2444680/how-do-i-add-my-own-custom-attributes-to-existing-built-in-python-types-like-a/2450942#2450942
    import ctypes as c

    class PyObject_HEAD(c.Structure):
        _fields_ = [
            ('HEAD', c.c_ubyte * (object.__basicsize__ -  c.sizeof(c.c_void_p))),
            ('ob_type', c.c_void_p)
        ]

    _get_dict = c.pythonapi._PyObject_GetDictPtr
    _get_dict.restype = c.POINTER(c.py_object)
    _get_dict.argtypes = [c.py_object]

    def get_dict(object):
        return _get_dict(object).contents.value

    get_dict(str)['format_map'] = format_map

""" String indentation """
try:
    import textwrap
    textwrap.indent
except AttributeError:  # undefined function (wasn't added until Python 3.3)
    def indent(text, prefix): # Currently not supporting predicate arg
        return ''.join(prefix+line for line in text.splitlines(True))
    get_dict(textwrap)["indent"] = indent