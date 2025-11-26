"""Upload repository job definition."""

from typing import Dict, List
from app.jobs.base import Job
from app.runtimes.base import JobResources
from app.config import get_config


class UploadRepoJob(Job):
    """
    Job for uploading a Git repository to Qdrant.

    This is a heavy workload that requires significant resources.
    """

    def __init__(
        self,
        job_name: str,
        repo_url: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        git_token: str = None,
        qdrant_host: str = None,
        qdrant_port: int = None
    ):
        """
        Initialize upload repository job.

        Args:
            job_name: Unique job identifier
            repo_url: Git repository URL
            collection_name: Qdrant collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding provider
            git_token: Optional Git token for private repos
            qdrant_host: Qdrant host (uses config default if None)
            qdrant_port: Qdrant port (uses config default if None)
        """
        super().__init__(job_name)
        self.repo_url = repo_url
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.api_token = api_token
        self.git_token = git_token

        config = get_config()
        self.qdrant_host = qdrant_host or config.qdrant_host
        self.qdrant_port = qdrant_port or config.qdrant_port

    def get_operation_name(self) -> str:
        return "upload_repo"

    def get_command(self) -> List[str]:
        """Get command to execute the upload."""
        # This will run the worker.py script with upload_repo operation
        cmd = [
            "python", "-m", "app.worker",
            "upload_repo",
            self.repo_url,
            self.collection_name
        ]

        if self.git_token:
            cmd.extend(["--git-token", self.git_token])

        return cmd

    def get_environment(self) -> Dict[str, str]:
        """Get environment variables for the job."""
        env = {
            "QDRANT_HOST": self.qdrant_host,
            "QDRANT_PORT": str(self.qdrant_port),
            "MODEL_NAME": self.embedding_model,
            "API_TOKEN": self.api_token,
        }

        if self.git_token:
            env["GITHUB_TOKEN"] = self.git_token

        return env

    def get_resources(self) -> JobResources:
        """Get resource requirements for repository upload."""
        # Repository uploads need substantial resources
        return JobResources(
            cpu="2",          # 2 CPU cores
            memory="4Gi",     # 4GB RAM
            timeout=3600      # 1 hour timeout
        )

    def get_image(self) -> str:
        """Get container image for this job."""
        config = get_config()
        return config.worker_image

    def get_metadata(self) -> Dict[str, str]:
        """Get job metadata."""
        return {
            **super().get_metadata(),
            "repo_url": self.repo_url,
            "collection": self.collection_name,
            "embedding_model": self.embedding_model,
            "workload_type": "heavy"
        }
