"""Plugins for skill execution: output handlers and response formatters."""

from .base import OutputFile, OutputHandler, ResponseFormatter
from .formatters import DefaultResponseFormatter
from .local import LocalOutputHandler

__all__ = [
    "OutputHandler",
    "OutputFile",
    "ResponseFormatter",
    "LocalOutputHandler",
    "DefaultResponseFormatter",
]

# Optional GCS handler - import separately if google-cloud-storage is installed
try:
    from .gcs import GCSOutputHandler  # noqa: F401

    __all__.append("GCSOutputHandler")
except ImportError:
    pass
