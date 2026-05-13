"""Plugins for skill execution: output handlers and response formatters."""

from .base import OutputHandler, OutputFile, ResponseFormatter
from .local import LocalOutputHandler
from .formatters import DefaultResponseFormatter

__all__ = [
    "OutputHandler",
    "OutputFile",
    "ResponseFormatter",
    "LocalOutputHandler",
    "DefaultResponseFormatter",
]

# Optional GCS handler - import separately if google-cloud-storage is installed
try:
    from .gcs import GCSOutputHandler

    __all__.append("GCSOutputHandler")
except ImportError:
    pass
