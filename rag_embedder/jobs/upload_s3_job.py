"""Upload S3 bucket job definition."""

from typing import Dict, List, Optional
from app.jobs.base import Job
from app.runtimes.base import JobResources
from app.config import get_config


class UploadS3Job(Job):
    """
    Job for uploading an S3 bucket to Qdrant.

    This is a heavy workload that requires significant resources.
    """

    def __init__(
        self,
        job_name: str,
        bucket_name: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        prefix: str = "",
        s3_endpoint: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: str = "us-east-1",
        qdrant_host: str = None,
        qdrant_port: int = None
    ):
        """
        Initialize upload S3 bucket job.

        Args:
            job_name: Unique job identifier
            bucket_name: S3 bucket name
            collection_name: Qdrant collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding provider
            prefix: S3 prefix/folder to download (optional)
            s3_endpoint: Custom S3 endpoint URL (optional)
            aws_access_key_id: AWS access key (optional)
            aws_secret_access_key: AWS secret key (optional)
            aws_region: AWS region (default: us-east-1)
            qdrant_host: Qdrant host (uses config default if None)
            qdrant_port: Qdrant port (uses config default if None)
        """
        super().__init__(job_name)
        self.bucket_name = bucket_name
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.api_token = api_token
        self.prefix = prefix
        self.s3_endpoint = s3_endpoint
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region

        config = get_config()
        self.qdrant_host = qdrant_host or config.qdrant_host
        self.qdrant_port = qdrant_port or config.qdrant_port

    def get_operation_name(self) -> str:
        return "upload_s3"

    def get_command(self) -> List[str]:
        """Get command to execute the upload."""
        # This will run the worker.py script with upload_s3 operation
        cmd = [
            "python", "-m", "app.worker",
            "upload_s3",
            self.bucket_name,
            self.collection_name
        ]

        if self.prefix:
            cmd.extend(["--prefix", self.prefix])

        if self.s3_endpoint:
            cmd.extend(["--endpoint", self.s3_endpoint])

        return cmd

    def get_environment(self) -> Dict[str, str]:
        """Get environment variables for the job."""
        env = {
            "QDRANT_HOST": self.qdrant_host,
            "QDRANT_PORT": str(self.qdrant_port),
            "MODEL_NAME": self.embedding_model,
            "API_TOKEN": self.api_token,
            "AWS_REGION": self.aws_region,
        }

        if self.aws_access_key_id:
            env["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id

        if self.aws_secret_access_key:
            env["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key

        return env

    def get_resources(self) -> JobResources:
        """Get resource requirements for S3 bucket upload."""
        # S3 downloads need resources similar to repos
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
            "bucket_name": self.bucket_name,
            "prefix": self.prefix,
            "collection": self.collection_name,
            "embedding_model": self.embedding_model,
            "workload_type": "heavy"
        }
