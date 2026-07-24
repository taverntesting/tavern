import warnings

# Suppress DeprecationWarnings from pkg_resources used by proto libraries.
# These come from transitive dependencies and are not actionable here.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")
