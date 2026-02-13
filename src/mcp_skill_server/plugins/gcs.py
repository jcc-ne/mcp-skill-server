"""Google Cloud Storage output handler.

This is an example implementation. Install google-cloud-storage to use:
    pip install google-cloud-storage
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote

from .base import OutputHandler, OutputFile

logger = logging.getLogger(__name__)

# Lazy import - only fail when actually used
_storage_client = None


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        try:
            from google.cloud import storage

            _storage_client = storage.Client()
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS uploads. "
                "Install with: pip install google-cloud-storage"
            )
    return _storage_client


class GCSOutputHandler(OutputHandler):
    """
    Upload output files to Google Cloud Storage.

    Features:
    - Content-based caching to avoid redundant uploads
    - Configurable bucket and folder prefix
    - Returns download URLs

    Example:
        handler = GCSOutputHandler(
            bucket_name="my-bucket",
            folder_prefix="skills/outputs/",
            base_url="https://my-api.example.com",
        )
    """

    def __init__(
        self,
        bucket_name: str,
        folder_prefix: str = "",
        base_url: str = "",
        download_endpoint: str = "/download?gcs_uri=",
        cache_file: Optional[Path] = None,
    ):
        """
        Initialize the GCS handler.

        Args:
            bucket_name: GCS bucket name
            folder_prefix: Folder prefix within the bucket
            base_url: Base URL for download links
            download_endpoint: Endpoint path for download links
            cache_file: Optional path to cache file for tracking uploads
        """
        self.bucket_name = bucket_name
        self.folder_prefix = folder_prefix.rstrip("/") + "/" if folder_prefix else ""
        self.base_url = base_url.rstrip("/")
        self.download_endpoint = download_endpoint
        self.cache_file = cache_file
        self._cache: Dict[str, str] = {}

        if cache_file and cache_file.exists():
            self._load_cache()

    def _load_cache(self):
        """Load upload cache from disk."""
        try:
            with open(self.cache_file, "r") as f:
                self._cache = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self._cache = {}

    def _save_cache(self):
        """Save upload cache to disk."""
        if not self.cache_file:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_cache_key(self, file_path: Path, file_hash: str) -> str:
        """Generate cache key for a file."""
        return f"{file_path}:{file_hash}"

    async def process(
        self,
        file_paths: List[Path],
        skill_name: str,
        skill_directory: Path,
    ) -> List[OutputFile]:
        """Upload files to GCS and return download URLs."""
        client = _get_storage_client()
        bucket = client.bucket(self.bucket_name)
        results = []

        for file_path in file_paths:
            try:
                file_hash = self._get_file_hash(file_path)
                cache_key = self._get_cache_key(file_path, file_hash)

                # Check cache
                gcs_uri = self._cache.get(cache_key)

                if not gcs_uri:
                    # Upload to GCS
                    blob_name = f"{self.folder_prefix}{skill_name}_{file_path.name}"
                    blob = bucket.blob(blob_name)

                    with open(file_path, "rb") as f:
                        blob.upload_from_file(f)

                    gcs_uri = f"gs://{self.bucket_name}/{blob_name}"

                    # Update cache
                    self._cache[cache_key] = gcs_uri
                    self._save_cache()

                    logger.info(f"Uploaded {file_path.name} to {gcs_uri}")
                else:
                    logger.info(f"Cache hit for {file_path.name}: {gcs_uri}")

                # Build download URL
                download_url = None
                if self.base_url:
                    download_url = (
                        f"{self.base_url}{self.download_endpoint}{quote(gcs_uri)}"
                    )

                results.append(
                    OutputFile(
                        filename=file_path.name,
                        local_path=file_path,
                        url=download_url,
                        metadata={"gcs_uri": gcs_uri},
                    )
                )

            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")
                # Still include the file but without URL
                results.append(
                    OutputFile(
                        filename=file_path.name,
                        local_path=file_path,
                        metadata={"error": str(e)},
                    )
                )

        return results
