"""
Base job definition for the RAG system.

Jobs define WHAT to execute (command, environment, resources).
Runtimes define HOW to execute (local, Docker, K8s, AWS).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.runtimes.base import JobResources


@dataclass
class JobDefinition:
    """
    Definition of a job to be executed.

    This is a data class that describes the job independently
    of how it will be executed.
    """
    name: str
    operation: str  # e.g., "upload_repo", "create_collection"
    command: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    resources: JobResources = field(default_factory=JobResources)
    image: Optional[str] = None  # Container image (if needed)
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate job definition."""
        if not self.name:
            raise ValueError("Job name is required")
        if not self.command:
            raise ValueError("Job command is required")


class Job(ABC):
    """
    Abstract base class for job types.

    Subclasses define specific job types (upload repo, create collection, etc.)
    and their resource requirements.
    """

    def __init__(self, job_name: str):
        """
        Initialize job.

        Args:
            job_name: Unique identifier for this job instance
        """
        self.job_name = job_name

    @abstractmethod
    def get_operation_name(self) -> str:
        """
        Get the operation name (e.g., 'upload_repo').

        Returns:
            Operation identifier
        """
        pass

    @abstractmethod
    def get_command(self) -> List[str]:
        """
        Get the command to execute.

        Returns:
            Command and arguments as list
        """
        pass

    @abstractmethod
    def get_environment(self) -> Dict[str, str]:
        """
        Get environment variables for the job.

        Returns:
            Environment variable dictionary
        """
        pass

    @abstractmethod
    def get_resources(self) -> JobResources:
        """
        Get resource requirements for the job.

        Returns:
            Resource requirements
        """
        pass

    def get_image(self) -> Optional[str]:
        """
        Get container image for containerized runtimes.

        Returns:
            Image name/tag or None for local execution
        """
        return None

    def get_metadata(self) -> Dict[str, str]:
        """
        Get job metadata (labels, tags, etc.).

        Returns:
            Metadata dictionary
        """
        return {
            "operation": self.get_operation_name(),
            "job_name": self.job_name
        }

    def to_definition(self) -> JobDefinition:
        """
        Convert job to a JobDefinition.

        Returns:
            JobDefinition instance
        """
        return JobDefinition(
            name=self.job_name,
            operation=self.get_operation_name(),
            command=self.get_command(),
            env=self.get_environment(),
            resources=self.get_resources(),
            image=self.get_image(),
            metadata=self.get_metadata()
        )
