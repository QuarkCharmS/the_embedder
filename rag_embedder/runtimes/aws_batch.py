"""
AWS Batch runtime for job execution.

Executes jobs as AWS Batch jobs.
Suitable for production workloads on AWS.
"""

import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from app.runtimes.base import JobRuntime, JobStatus, JobResult, JobResources


class AWSBatchRuntime(JobRuntime):
    """
    Execute jobs using AWS Batch.

    Requires boto3 and AWS credentials to be configured.
    """

    def __init__(
        self,
        job_queue: str,
        job_definition: str,
        region: str = "us-east-1"
    ):
        """
        Initialize AWS Batch runtime.

        Args:
            job_queue: AWS Batch job queue name
            job_definition: AWS Batch job definition name
            region: AWS region
        """
        try:
            import boto3
            self.boto3 = boto3
            self.batch_client = boto3.client("batch", region_name=region)
            self.logs_client = boto3.client("logs", region_name=region)
            self.job_queue = job_queue
            self.job_definition = job_definition
            self.region = region
        except ImportError:
            raise RuntimeError(
                "boto3 not installed. Install with: pip install boto3"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize AWS clients: {e}")

    def _parse_resources(self, resources: JobResources) -> Dict:
        """Convert JobResources to AWS Batch resource requirements."""
        # Parse CPU (vCPUs)
        vcpus = int(float(resources.cpu))

        # Parse memory in MiB
        memory_str = resources.memory
        if memory_str.endswith("Gi"):
            memory_mib = int(memory_str[:-2]) * 1024
        elif memory_str.endswith("Mi"):
            memory_mib = int(memory_str[:-2])
        else:
            memory_mib = int(memory_str) // (1024 * 1024)  # Assume bytes

        resource_requirements = [
            {"type": "VCPU", "value": str(vcpus)},
            {"type": "MEMORY", "value": str(memory_mib)}
        ]

        if resources.gpu > 0:
            resource_requirements.append({
                "type": "GPU",
                "value": str(resources.gpu)
            })

        return {
            "resourceRequirements": resource_requirements,
            "timeout": {"attemptDurationSeconds": resources.timeout}
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
        """Submit job to AWS Batch."""
        # AWS Batch job names must be unique and DNS-compatible
        job_id = f"{job_name}-{uuid.uuid4().hex[:8]}"

        # Convert env dict to AWS format
        environment = [{"name": k, "value": v} for k, v in env.items()]

        # Parse resources
        resource_overrides = self._parse_resources(resources)

        try:
            response = self.batch_client.submit_job(
                jobName=job_id,
                jobQueue=self.job_queue,
                jobDefinition=self.job_definition,
                containerOverrides={
                    "command": command,
                    "environment": environment,
                    **resource_overrides
                },
                tags={
                    "job_name": job_name,
                    "managed_by": "rag-runtime"
                }
            )

            # Return the AWS Batch job ID
            return response["jobId"]

        except Exception as e:
            raise RuntimeError(f"Failed to submit AWS Batch job: {e}")

    def get_status(self, job_id: str) -> JobStatus:
        """Get job status from AWS Batch."""
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])

            if not response["jobs"]:
                return JobStatus.UNKNOWN

            job = response["jobs"][0]
            status_str = job["status"]

            # Map AWS Batch status to JobStatus
            status_map = {
                "SUBMITTED": JobStatus.SUBMITTED,
                "PENDING": JobStatus.PENDING,
                "RUNNABLE": JobStatus.PENDING,
                "STARTING": JobStatus.PENDING,
                "RUNNING": JobStatus.RUNNING,
                "SUCCEEDED": JobStatus.SUCCEEDED,
                "FAILED": JobStatus.FAILED
            }

            return status_map.get(status_str, JobStatus.UNKNOWN)

        except Exception:
            return JobStatus.UNKNOWN

    def get_result(self, job_id: str) -> JobResult:
        """Get job result from AWS Batch."""
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])

            if not response["jobs"]:
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.UNKNOWN,
                    error="Job not found"
                )

            job = response["jobs"][0]
            status = self.get_status(job_id)

            # Parse timestamps
            started_at = None
            finished_at = None
            if "startedAt" in job:
                started_at = datetime.fromtimestamp(job["startedAt"] / 1000)
            if "stoppedAt" in job:
                finished_at = datetime.fromtimestamp(job["stoppedAt"] / 1000)

            # Get exit code and error
            exit_code = None
            error = None
            if "container" in job:
                exit_code = job["container"].get("exitCode")
                error = job["container"].get("reason")

            # Get logs (if available)
            output = None
            if "container" in job and "logStreamName" in job["container"]:
                log_stream = job["container"]["logStreamName"]
                log_group = "/aws/batch/job"
                try:
                    logs_response = self.logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=log_stream,
                        limit=100
                    )
                    output = "\n".join([
                        event["message"] for event in logs_response["events"]
                    ])
                except Exception:
                    pass  # Logs may not be available yet

            return JobResult(
                job_id=job_id,
                status=status,
                output=output,
                error=error,
                exit_code=exit_code,
                started_at=started_at,
                finished_at=finished_at,
                metadata={
                    "job_name": job["jobName"],
                    "job_queue": job["jobQueue"],
                    "job_definition": job["jobDefinition"]
                }
            )

        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error=f"Error getting result: {e}"
            )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel AWS Batch job."""
        try:
            self.batch_client.terminate_job(
                jobId=job_id,
                reason="Cancelled by user"
            )
            return True
        except Exception:
            return False

    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs from CloudWatch."""
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])

            if not response["jobs"]:
                return f"Job {job_id} not found"

            job = response["jobs"][0]

            if "container" not in job or "logStreamName" not in job["container"]:
                return "Logs not available yet"

            log_stream = job["container"]["logStreamName"]
            log_group = "/aws/batch/job"

            logs_response = self.logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                limit=tail
            )

            logs = [event["message"] for event in logs_response["events"]]
            return "\n".join(logs)

        except Exception as e:
            return f"Error getting logs: {e}"

    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 10
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
        """
        Clean up job resources.

        Note: AWS Batch automatically cleans up after jobs.
        This is a no-op but provided for interface compatibility.
        """
        return True
