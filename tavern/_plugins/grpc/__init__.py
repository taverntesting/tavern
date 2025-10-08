"""
Tavern gRPC Plugin

This module provides gRPC functionality for the Tavern testing framework.
It handles gRPC request and response processing for API testing.

The module contains classes and functions for building and sending gRPC requests
and processing gRPC responses for API testing scenarios.
"""

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
