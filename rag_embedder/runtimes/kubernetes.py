"""
Kubernetes runtime for job execution.

Executes jobs as Kubernetes Jobs.
Suitable for production workloads on K8s clusters.
"""

import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from app.runtimes.base import JobRuntime, JobStatus, JobResult, JobResources


class KubernetesRuntime(JobRuntime):
    """
    Execute jobs using Kubernetes Jobs API.

    Requires kubernetes Python client and cluster access.
    """

    def __init__(
        self,
        namespace: str = "default",
        service_account: Optional[str] = None,
        image_pull_secrets: Optional[List[str]] = None
    ):
        """
        Initialize Kubernetes runtime.

        Args:
            namespace: K8s namespace for jobs
            service_account: Service account for job pods
            image_pull_secrets: Image pull secrets for private registries
        """
        try:
            from kubernetes import client, config
            # Try to load in-cluster config first, then kubeconfig
            try:
                config.load_incluster_config()
            except:
                config.load_kube_config()

            self.batch_v1 = client.BatchV1Api()
            self.core_v1 = client.CoreV1Api()
            self.namespace = namespace
            self.service_account = service_account
            self.image_pull_secrets = image_pull_secrets or []
        except ImportError:
            raise RuntimeError(
                "Kubernetes client not installed. Install with: pip install kubernetes"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Kubernetes client: {e}")

    def _parse_resources(self, resources: JobResources) -> Dict:
        """Convert JobResources to K8s resource requirements."""
        return {
            "requests": {
                "cpu": resources.cpu,
                "memory": resources.memory
            },
            "limits": {
                "cpu": resources.cpu,
                "memory": resources.memory
            }
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
        """Submit job to Kubernetes."""
        if not image:
            raise ValueError("Kubernetes runtime requires 'image' parameter")

        from kubernetes import client

        # K8s job names must be DNS-compatible
        job_id = f"{job_name}-{uuid.uuid4().hex[:8]}"

        # Convert env dict to K8s format
        env_vars = [
            client.V1EnvVar(name=k, value=v)
            for k, v in env.items()
        ]

        # Parse resources
        resource_requirements = self._parse_resources(resources)

        # Build container spec
        container = client.V1Container(
            name="worker",
            image=image,
            command=command,
            env=env_vars,
            resources=client.V1ResourceRequirements(**resource_requirements)
        )

        # Build pod spec
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never"
        )

        if self.service_account:
            pod_spec.service_account_name = self.service_account

        if self.image_pull_secrets:
            pod_spec.image_pull_secrets = [
                client.V1LocalObjectReference(name=secret)
                for secret in self.image_pull_secrets
            ]

        # Build pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"job-name": job_id, "managed-by": "rag-runtime"}
            ),
            spec=pod_spec
        )

        # Build job spec
        job_spec = client.V1JobSpec(
            template=pod_template,
            backoff_limit=3,
            ttl_seconds_after_finished=3600,  # Clean up after 1 hour
            active_deadline_seconds=resources.timeout
        )

        # Build job
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_id,
                labels={"job-name": job_name, "managed-by": "rag-runtime"}
            ),
            spec=job_spec
        )

        try:
            self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job
            )
            return job_id

        except Exception as e:
            raise RuntimeError(f"Failed to create Kubernetes job: {e}")

    def get_status(self, job_id: str) -> JobStatus:
        """Get job status from Kubernetes."""
        try:
            job = self.batch_v1.read_namespaced_job(
                name=job_id,
                namespace=self.namespace
            )

            status = job.status

            # Check conditions
            if status.succeeded:
                return JobStatus.SUCCEEDED
            elif status.failed:
                return JobStatus.FAILED
            elif status.active:
                return JobStatus.RUNNING
            else:
                return JobStatus.PENDING

        except Exception:
            return JobStatus.UNKNOWN

    def get_result(self, job_id: str) -> JobResult:
        """Get job result from Kubernetes."""
        try:
            job = self.batch_v1.read_namespaced_job(
                name=job_id,
                namespace=self.namespace
            )

            status = self.get_status(job_id)

            # Parse timestamps
            started_at = None
            finished_at = None
            if job.status.start_time:
                started_at = job.status.start_time
            if job.status.completion_time:
                finished_at = job.status.completion_time

            # Get pod logs if available
            output = None
            error = None
            try:
                # List pods for this job
                pods = self.core_v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f"job-name={job_id}"
                )

                if pods.items:
                    pod = pods.items[0]
                    pod_name = pod.metadata.name

                    # Get pod logs
                    output = self.core_v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        tail_lines=100
                    )

                    # Check for pod failures
                    if pod.status.container_statuses:
                        container_status = pod.status.container_statuses[0]
                        if container_status.state.terminated:
                            if container_status.state.terminated.reason:
                                error = container_status.state.terminated.reason

            except Exception:
                pass  # Logs may not be available

            return JobResult(
                job_id=job_id,
                status=status,
                output=output,
                error=error,
                started_at=started_at,
                finished_at=finished_at,
                metadata={
                    "namespace": self.namespace,
                    "succeeded": job.status.succeeded or 0,
                    "failed": job.status.failed or 0
                }
            )

        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error=f"Error getting result: {e}"
            )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel Kubernetes job."""
        from kubernetes import client

        try:
            # Delete job (with propagation policy to delete pods)
            self.batch_v1.delete_namespaced_job(
                name=job_id,
                namespace=self.namespace,
                propagation_policy="Background"
            )
            return True
        except Exception:
            return False

    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs from Kubernetes."""
        try:
            # List pods for this job
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"job-name={job_id}"
            )

            if not pods.items:
                return f"No pods found for job {job_id}"

            pod_name = pods.items[0].metadata.name

            # Get pod logs
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                tail_lines=tail
            )

            return logs

        except Exception as e:
            return f"Error getting logs: {e}"

    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 5
    ) -> JobResult:
        """Wait for job completion."""
        start_time = time.time()

        while True:
            status = self.get_status(job_id)

            if status in [JobStatus.SUCCEEDED, JobStatus.FAILED]:
                return self.get_result(job_id)

            if timeout and (time.time() - start_time) > timeout:
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.UNKNOWN,
                    error="Timeout waiting for job completion"
                )

            time.sleep(poll_interval)

    def cleanup(self, job_id: str) -> bool:
        """Clean up Kubernetes job."""
        from kubernetes import client

        try:
            self.batch_v1.delete_namespaced_job(
                name=job_id,
                namespace=self.namespace,
                propagation_policy="Background"
            )
            return True
        except Exception:
            return False
