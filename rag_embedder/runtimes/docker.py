"""
Docker runtime for job execution.

Executes jobs as Docker containers using the Docker SDK.
Suitable for local development with container isolation.
"""

import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from app.runtimes.base import JobRuntime, JobStatus, JobResult, JobResources


class DockerRuntime(JobRuntime):
    """
    Execute jobs as Docker containers.

    Requires Docker daemon to be running and docker SDK installed.
    """

    def __init__(self, network: str = "bridge"):
        """
        Initialize Docker runtime.

        Args:
            network: Docker network to use (default: bridge)
        """
        try:
            import docker
            self.docker = docker
            self.client = docker.from_env()
            self.network = network
        except ImportError:
            raise RuntimeError(
                "Docker SDK not installed. Install with: pip install docker"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e}")

    def _parse_resources(self, resources: JobResources) -> Dict:
        """Convert JobResources to Docker resource constraints."""
        # Parse CPU (e.g., "1" = 1 core, "0.5" = 0.5 cores)
        cpu_quota = int(float(resources.cpu) * 100000)  # Docker uses microseconds

        # Parse memory (e.g., "1Gi" = 1073741824 bytes, "512Mi" = 536870912 bytes)
        memory_str = resources.memory
        if memory_str.endswith("Gi"):
            memory_bytes = int(memory_str[:-2]) * 1024 * 1024 * 1024
        elif memory_str.endswith("Mi"):
            memory_bytes = int(memory_str[:-2]) * 1024 * 1024
        else:
            memory_bytes = int(memory_str)  # Assume bytes

        return {
            "cpu_quota": cpu_quota,
            "cpu_period": 100000,
            "mem_limit": memory_bytes
        }

    def submit_job(
        self,
        job_name: str,
        command: List[str],
        env: Dict[str, str],
        resources: JobResources,
        image: Optional[str] = None,
        **kwargs
    ) -> str:
        """Submit job as Docker container."""
        if not image:
            raise ValueError("Docker runtime requires 'image' parameter")

        job_id = f"{job_name}-{uuid.uuid4().hex[:8]}"
        docker_resources = self._parse_resources(resources)

        try:
            # Ensure network exists
            if self.network != "bridge" and self.network != "host":
                try:
                    self.client.networks.get(self.network)
                except self.docker.errors.NotFound:
                    # Create network if it doesn't exist
                    self.client.networks.create(self.network, driver="bridge")

            # Run container
            container = self.client.containers.run(
                image=image,
                command=command,
                environment=env,
                name=job_id,
                network=self.network,
                detach=True,
                remove=False,  # Keep container for log retrieval
                labels={
                    "job_name": job_name,
                    "managed_by": "rag-runtime"
                },
                **docker_resources
            )

            return job_id

        except self.docker.errors.ImageNotFound:
            raise RuntimeError(f"Docker image not found: {image}")
        except Exception as e:
            raise RuntimeError(f"Failed to start Docker container: {e}")

    def get_status(self, job_id: str) -> JobStatus:
        """Get job status."""
        try:
            container = self.client.containers.get(job_id)
            status = container.status

            if status == "running":
                return JobStatus.RUNNING
            elif status == "exited":
                exit_code = container.attrs["State"]["ExitCode"]
                return JobStatus.SUCCEEDED if exit_code == 0 else JobStatus.FAILED
            elif status == "created":
                return JobStatus.PENDING
            else:
                return JobStatus.UNKNOWN

        except self.docker.errors.NotFound:
            return JobStatus.UNKNOWN
        except Exception:
            return JobStatus.UNKNOWN

    def get_result(self, job_id: str) -> JobResult:
        """Get job result."""
        try:
            container = self.client.containers.get(job_id)
            status = self.get_status(job_id)

            # Get container info
            attrs = container.attrs
            state = attrs["State"]

            # Parse timestamps
            started_at = None
            finished_at = None
            if state.get("StartedAt"):
                started_at = datetime.fromisoformat(state["StartedAt"].replace("Z", "+00:00"))
            if state.get("FinishedAt") and state["FinishedAt"] != "0001-01-01T00:00:00Z":
                finished_at = datetime.fromisoformat(state["FinishedAt"].replace("Z", "+00:00"))

            # Get logs
            logs = container.logs(timestamps=False).decode("utf-8", errors="replace")

            return JobResult(
                job_id=job_id,
                status=status,
                output=logs,
                error=state.get("Error") or None,
                exit_code=state.get("ExitCode"),
                started_at=started_at,
                finished_at=finished_at,
                metadata={
                    "image": attrs["Config"]["Image"],
                    "container_id": container.id
                }
            )

        except self.docker.errors.NotFound:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error="Container not found"
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error=f"Error getting result: {e}"
            )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job."""
        try:
            container = self.client.containers.get(job_id)
            if container.status == "running":
                container.stop(timeout=10)
                return True
            return False
        except self.docker.errors.NotFound:
            return False
        except Exception:
            return False

    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs."""
        try:
            container = self.client.containers.get(job_id)
            logs = container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
            return logs
        except self.docker.errors.NotFound:
            return f"Container {job_id} not found"
        except Exception as e:
            return f"Error getting logs: {e}"

    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 5
    ) -> JobResult:
        """Wait for job completion."""
        try:
            container = self.client.containers.get(job_id)

            # Wait for container to finish
            result = container.wait(timeout=timeout)
            return self.get_result(job_id)

        except self.docker.errors.NotFound:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error="Container not found"
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error=f"Error waiting for completion: {e}"
            )

    def cleanup(self, job_id: str) -> bool:
        """Clean up job resources."""
        try:
            container = self.client.containers.get(job_id)
            container.remove(force=True)
            return True
        except self.docker.errors.NotFound:
            return False
        except Exception:
            return False
