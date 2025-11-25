"""Collection management job definition."""

from typing import Dict, List
from app.jobs.base import Job
from app.runtimes.base import JobResources
from app.config import get_config


class CollectionJob(Job):
    """
    Job for collection management operations (create, delete, list).

    This is a lightweight workload that can run with minimal resources.
    """

    def __init__(
        self,
        job_name: str,
        operation: str,  # "create", "delete", "list"
        collection_name: str = None,
        dimension: int = None,
        qdrant_host: str = None,
        qdrant_port: int = None
    ):
        """
        Initialize collection management job.

        Args:
            job_name: Unique job identifier
            operation: Operation type ("create", "delete", "list")
            collection_name: Collection name (required for create/delete)
            dimension: Vector dimension (required for create)
            qdrant_host: Qdrant host (uses config default if None)
            qdrant_port: Qdrant port (uses config default if None)
        """
        super().__init__(job_name)
        self.operation = operation
        self.collection_name = collection_name
        self.dimension = dimension

        config = get_config()
        self.qdrant_host = qdrant_host or config.qdrant_host
        self.qdrant_port = qdrant_port or config.qdrant_port

        # Validate
        if operation in ["create", "delete"] and not collection_name:
            raise ValueError(f"collection_name required for {operation} operation")
        if operation == "create" and not dimension:
            raise ValueError("dimension required for create operation")

    def get_operation_name(self) -> str:
        return f"collection_{self.operation}"

    def get_command(self) -> List[str]:
        """Get command to execute the collection operation."""
        cmd = ["python", "-m", "app.worker", f"collection_{self.operation}"]

        if self.operation == "create":
            cmd.extend([self.collection_name, str(self.dimension)])
        elif self.operation == "delete":
            cmd.append(self.collection_name)

        return cmd

    def get_environment(self) -> Dict[str, str]:
        """Get environment variables for the job."""
        return {
            "QDRANT_HOST": self.qdrant_host,
            "QDRANT_PORT": str(self.qdrant_port),
        }

    def get_resources(self) -> JobResources:
        """Get resource requirements for collection operations."""
        # Collection operations are very lightweight
        return JobResources(
            cpu="0.25",       # 0.25 CPU cores
            memory="256Mi",   # 256MB RAM
            timeout=300       # 5 min timeout
        )

    def get_image(self) -> str:
        """
        Get container image for this job.

        Note: For lightweight ops, you might want a different (smaller) image.
        For now, uses the same worker image.
        """
        config = get_config()
        return config.worker_image

    def get_metadata(self) -> Dict[str, str]:
        """Get job metadata."""
        metadata = {
            **super().get_metadata(),
            "operation_type": self.operation,
            "workload_type": "light"
        }

        if self.collection_name:
            metadata["collection"] = self.collection_name
        if self.dimension:
            metadata["dimension"] = str(self.dimension)

        return metadata
