"""Upload file/archive job definition."""

from typing import Dict, List
from app.jobs.base import Job
from app.runtimes.base import JobResources
from app.config import get_config


class UploadFileJob(Job):
    """
    Job for uploading a file or archive to Qdrant.

    Moderate workload - less intensive than repository upload.
    """

    def __init__(
        self,
        job_name: str,
        file_path: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        upload_type: str = "file",  # "file" or "archive"
        qdrant_host: str = None,
        qdrant_port: int = None
    ):
        """
        Initialize upload file job.

        Args:
            job_name: Unique job identifier
            file_path: Path to file/archive
            collection_name: Qdrant collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding provider
            upload_type: Type of upload ("file" or "archive")
            qdrant_host: Qdrant host (uses config default if None)
            qdrant_port: Qdrant port (uses config default if None)
        """
        super().__init__(job_name)
        self.file_path = file_path
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.api_token = api_token
        self.upload_type = upload_type

        config = get_config()
        self.qdrant_host = qdrant_host or config.qdrant_host
        self.qdrant_port = qdrant_port or config.qdrant_port

    def get_operation_name(self) -> str:
        return f"upload_{self.upload_type}"

    def get_command(self) -> List[str]:
        """Get command to execute the upload."""
        return [
            "python", "-m", "app.worker",
            f"upload_{self.upload_type}",
            self.file_path,
            self.collection_name
        ]

    def get_environment(self) -> Dict[str, str]:
        """Get environment variables for the job."""
        return {
            "QDRANT_HOST": self.qdrant_host,
            "QDRANT_PORT": str(self.qdrant_port),
            "MODEL_NAME": self.embedding_model,
            "API_TOKEN": self.api_token,
        }

    def get_resources(self) -> JobResources:
        """Get resource requirements for file upload."""
        # File uploads need moderate resources
        return JobResources(
            cpu="1",          # 1 CPU core
            memory="2Gi",     # 2GB RAM
            timeout=1800      # 30 min timeout
        )

    def get_image(self) -> str:
        """Get container image for this job."""
        config = get_config()
        return config.worker_image

    def get_metadata(self) -> Dict[str, str]:
        """Get job metadata."""
        return {
            **super().get_metadata(),
            "file_path": self.file_path,
            "collection": self.collection_name,
            "embedding_model": self.embedding_model,
            "upload_type": self.upload_type,
            "workload_type": "medium"
        }
