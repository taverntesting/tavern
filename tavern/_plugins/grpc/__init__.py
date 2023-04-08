import warnings

# Shut up warnings caused by proto libraries
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="pkg_resources", lineno=2804
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="pkg_resources", lineno=2309
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="pkg_resources", lineno=2870
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="pkg_resources", lineno=2349
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="pkg_resources", lineno=20
)
