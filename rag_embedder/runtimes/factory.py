"""
Runtime factory for selecting and creating job runtimes.

Automatically selects the appropriate runtime based on configuration.
"""

from typing import Optional

from app.config import Config, RuntimeBackend, get_config
from app.runtimes.base import JobRuntime
from app.runtimes.local import LocalRuntime
from app.runtimes.docker import DockerRuntime
from app.runtimes.kubernetes import KubernetesRuntime
from app.runtimes.aws_batch import AWSBatchRuntime


class RuntimeFactory:
    """
    Factory for creating job runtimes.

    Selects the appropriate runtime implementation based on configuration.
    """

    @staticmethod
    def create_runtime(config: Optional[Config] = None) -> JobRuntime:
        """
        Create a runtime instance based on configuration.

        Args:
            config: Configuration (uses global config if None)

        Returns:
            JobRuntime instance

        Raises:
            ValueError: If backend is not supported or misconfigured
        """
        if config is None:
            config = get_config()

        # Validate configuration
        config.validate_for_backend()

        backend = config.backend

        if backend == RuntimeBackend.LOCAL:
            return LocalRuntime()

        elif backend == RuntimeBackend.DOCKER:
            return DockerRuntime(network=config.docker_network)

        elif backend == RuntimeBackend.KUBERNETES:
            return KubernetesRuntime(
                namespace=config.k8s_namespace,
                service_account=config.k8s_service_account,
                image_pull_secrets=(
                    config.k8s_image_pull_secrets.split(",")
                    if config.k8s_image_pull_secrets
                    else None
                )
            )

        elif backend == RuntimeBackend.AWS_BATCH:
            return AWSBatchRuntime(
                job_queue=config.aws_batch_job_queue,
                job_definition=config.aws_batch_job_definition,
                region=config.aws_region
            )

        else:
            raise ValueError(f"Unsupported runtime backend: {backend}")

    @staticmethod
    def get_available_backends() -> list:
        """
        Get list of available runtime backends.

        Returns:
            List of backend names
        """
        return [backend.value for backend in RuntimeBackend]


# Global runtime instance (singleton pattern)
_runtime: Optional[JobRuntime] = None


def get_runtime() -> JobRuntime:
    """
    Get global runtime instance (singleton).

    Creates runtime on first call, reuses on subsequent calls.

    Returns:
        JobRuntime instance
    """
    global _runtime
    if _runtime is None:
        _runtime = RuntimeFactory.create_runtime()
    return _runtime


def reload_runtime() -> JobRuntime:
    """
    Reload runtime (useful for testing or config changes).

    Returns:
        New JobRuntime instance
    """
    global _runtime
    _runtime = RuntimeFactory.create_runtime()
    return _runtime
