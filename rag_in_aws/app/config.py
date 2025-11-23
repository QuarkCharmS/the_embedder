"""
Configuration management for the RAG system.

Handles environment detection and configuration loading.
"""

import os
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class RuntimeBackend(Enum):
    """Available runtime backends."""
    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    AWS_BATCH = "aws_batch"
    AWS_ECS = "aws_ecs"


@dataclass
class Config:
    """
    Application configuration.

    Loaded from environment variables with sensible defaults.
    """

    # Runtime configuration
    backend: RuntimeBackend = RuntimeBackend.LOCAL
    worker_image: str = "rag-worker:latest"

    # Qdrant configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Model configuration (defaults)
    default_model: Optional[str] = None
    default_api_token: Optional[str] = None

    # Docker configuration
    docker_network: str = "rag-network"

    # Kubernetes configuration
    k8s_namespace: str = "default"
    k8s_service_account: Optional[str] = None
    k8s_image_pull_secrets: Optional[str] = None

    # AWS configuration
    aws_region: str = "us-east-1"
    aws_batch_job_queue: Optional[str] = None
    aws_batch_job_definition: Optional[str] = None
    aws_ecs_cluster: Optional[str] = None
    aws_ecs_task_definition: Optional[str] = None
    aws_ecs_subnets: Optional[str] = None  # Comma-separated
    aws_ecs_security_groups: Optional[str] = None  # Comma-separated

    # Job defaults
    job_timeout: int = 3600  # 1 hour
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Returns:
            Config instance
        """
        # Determine backend
        backend_str = os.getenv("RUNTIME_BACKEND", "local").lower()
        try:
            backend = RuntimeBackend(backend_str)
        except ValueError:
            import logging
            logging.warning(f"Invalid RUNTIME_BACKEND '{backend_str}', using 'local'")
            backend = RuntimeBackend.LOCAL

        return cls(
            # Runtime
            backend=backend,
            worker_image=os.getenv("WORKER_IMAGE", "rag-worker:latest"),

            # Qdrant
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),

            # Model defaults
            default_model=os.getenv("MODEL_NAME"),
            default_api_token=os.getenv("API_TOKEN"),

            # Docker
            docker_network=os.getenv("DOCKER_NETWORK", "rag-network"),

            # Kubernetes
            k8s_namespace=os.getenv("K8S_NAMESPACE", "default"),
            k8s_service_account=os.getenv("K8S_SERVICE_ACCOUNT"),
            k8s_image_pull_secrets=os.getenv("K8S_IMAGE_PULL_SECRETS"),

            # AWS
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_batch_job_queue=os.getenv("AWS_BATCH_JOB_QUEUE"),
            aws_batch_job_definition=os.getenv("AWS_BATCH_JOB_DEFINITION"),
            aws_ecs_cluster=os.getenv("AWS_ECS_CLUSTER"),
            aws_ecs_task_definition=os.getenv("AWS_ECS_TASK_DEFINITION"),
            aws_ecs_subnets=os.getenv("AWS_ECS_SUBNETS"),
            aws_ecs_security_groups=os.getenv("AWS_ECS_SECURITY_GROUPS"),

            # Job defaults
            job_timeout=int(os.getenv("JOB_TIMEOUT", "3600")),
            max_retries=int(os.getenv("MAX_RETRIES", "3"))
        )

    def get_qdrant_url(self) -> str:
        """Get Qdrant connection URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    def validate_for_backend(self) -> bool:
        """
        Validate configuration for the selected backend.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If required configuration is missing
        """
        if self.backend == RuntimeBackend.AWS_BATCH:
            if not self.aws_batch_job_queue:
                raise ValueError("AWS_BATCH_JOB_QUEUE is required for AWS Batch backend")
            if not self.aws_batch_job_definition:
                raise ValueError("AWS_BATCH_JOB_DEFINITION is required for AWS Batch backend")

        elif self.backend == RuntimeBackend.AWS_ECS:
            if not self.aws_ecs_cluster:
                raise ValueError("AWS_ECS_CLUSTER is required for AWS ECS backend")
            if not self.aws_ecs_task_definition:
                raise ValueError("AWS_ECS_TASK_DEFINITION is required for AWS ECS backend")
            if not self.aws_ecs_subnets:
                raise ValueError("AWS_ECS_SUBNETS is required for AWS ECS backend")

        elif self.backend == RuntimeBackend.KUBERNETES:
            # K8s config validated by kubernetes runtime
            pass

        return True


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Config singleton
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """
    Reload configuration from environment.

    Returns:
        New config instance
    """
    global _config
    _config = Config.from_env()
    return _config
