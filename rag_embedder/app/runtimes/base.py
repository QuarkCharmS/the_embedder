"""
Base runtime abstractions for multi-environment job execution.

This module defines the core interfaces for running jobs across
different execution environments (local, Docker, Kubernetes, AWS).
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class JobResources:
    """Resource requirements for a job."""
    cpu: str = "1"           # CPU cores (e.g., "1", "2", "0.5")
    memory: str = "1Gi"      # Memory (e.g., "512Mi", "2Gi")
    gpu: int = 0             # Number of GPUs
    timeout: int = 3600      # Timeout in seconds


@dataclass
class JobResult:
    """Result of a job execution."""
    job_id: str
    status: JobStatus
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class JobRuntime(ABC):
    """
    Abstract base class for job execution runtimes.

    Implementations handle job execution in different environments:
    - LocalRuntime: subprocess execution
    - DockerRuntime: Docker containers
    - KubernetesRuntime: K8s Jobs
    - AWSBatchRuntime: AWS Batch jobs
    """

    @abstractmethod
    def submit_job(
        self,
        job_name: str,
        command: List[str],
        env: Dict[str, str],
        resources: JobResources,
        image: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Submit a job for execution.

        Args:
            job_name: Unique name for the job
            command: Command and arguments to execute
            env: Environment variables
            resources: Resource requirements
            image: Container image (for containerized runtimes)
            **kwargs: Runtime-specific parameters

        Returns:
            Job ID (unique identifier for tracking)
        """
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> JobStatus:
        """
        Get current status of a job.

        Args:
            job_id: Job identifier

        Returns:
            Current job status
        """
        pass

    @abstractmethod
    def get_result(self, job_id: str) -> JobResult:
        """
        Get detailed result of a job.

        Args:
            job_id: Job identifier

        Returns:
            Job result with output, errors, status
        """
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running or pending job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        pass

    @abstractmethod
    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """
        Get job logs.

        Args:
            job_id: Job identifier
            tail: Number of lines to retrieve (from end)

        Returns:
            Job logs as string
        """
        pass

    @abstractmethod
    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 5
    ) -> JobResult:
        """
        Wait for job to complete.

        Args:
            job_id: Job identifier
            timeout: Max wait time in seconds (None = no timeout)
            poll_interval: Seconds between status checks

        Returns:
            Final job result
        """
        pass

    @abstractmethod
    def cleanup(self, job_id: str) -> bool:
        """
        Clean up job resources.

        Args:
            job_id: Job identifier

        Returns:
            True if cleanup successful
        """
        pass
