def strtobool(val: str) -> bool:
    """Copied and slightly modified from distutils as it's being removed in a future version of
    Python"""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError(f"invalid truth value {val!r}")
