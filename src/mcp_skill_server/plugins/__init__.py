"""Output handler plugins for skill execution results."""

from .base import OutputHandler
from .local import LocalOutputHandler

__all__ = ["OutputHandler", "LocalOutputHandler"]

# Optional GCS handler - import separately if google-cloud-storage is installed
try:
    from .gcs import GCSOutputHandler
    __all__.append("GCSOutputHandler")
except ImportError:
    pass
