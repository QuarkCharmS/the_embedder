"""
Local subprocess runtime for job execution.

Executes jobs as local subprocesses on the same machine.
Suitable for development and testing.
"""

import subprocess
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import os

from app.runtimes.base import JobRuntime, JobStatus, JobResult, JobResources


class LocalRuntime(JobRuntime):
    """
    Execute jobs as local subprocesses.

    Jobs run directly on the host machine. Output is captured and stored.
    """

    def __init__(self, work_dir: Optional[Path] = None):
        """
        Initialize local runtime.

        Args:
            work_dir: Working directory for job execution (default: /tmp/rag-jobs)
        """
        self.work_dir = work_dir or Path("/tmp/rag-jobs")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, Dict] = {}  # In-memory job tracking

    def _get_job_dir(self, job_id: str) -> Path:
        """Get directory for job files."""
        job_dir = self.work_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def submit_job(
        self,
        job_name: str,
        command: List[str],
        env: Dict[str, str],
        resources: JobResources,
        image: Optional[str] = None,
        **kwargs
    ) -> str:
        """Submit job as subprocess."""
        job_id = f"{job_name}-{uuid.uuid4().hex[:8]}"
        job_dir = self._get_job_dir(job_id)

        # Merge environment
        full_env = os.environ.copy()
        full_env.update(env)

        # Store job metadata
        self._jobs[job_id] = {
            "name": job_name,
            "command": command,
            "env": env,
            "status": JobStatus.SUBMITTED,
            "submitted_at": datetime.now(),
            "process": None,
            "stdout_file": job_dir / "stdout.log",
            "stderr_file": job_dir / "stderr.log",
            "exit_code": None
        }

        # Start subprocess
        stdout_f = open(self._jobs[job_id]["stdout_file"], "w")
        stderr_f = open(self._jobs[job_id]["stderr_file"], "w")

        try:
            process = subprocess.Popen(
                command,
                env=full_env,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=str(job_dir)
            )
            self._jobs[job_id]["process"] = process
            self._jobs[job_id]["status"] = JobStatus.RUNNING
            self._jobs[job_id]["started_at"] = datetime.now()

        except Exception as e:
            self._jobs[job_id]["status"] = JobStatus.FAILED
            self._jobs[job_id]["error"] = str(e)
            stdout_f.close()
            stderr_f.close()
            raise

        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        """Get job status."""
        if job_id not in self._jobs:
            return JobStatus.UNKNOWN

        job = self._jobs[job_id]
        process = job.get("process")

        if process is None:
            return job["status"]

        # Check if process finished
        exit_code = process.poll()
        if exit_code is not None:
            job["exit_code"] = exit_code
            job["finished_at"] = datetime.now()
            job["status"] = JobStatus.SUCCEEDED if exit_code == 0 else JobStatus.FAILED
            # Close file handles
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

        return job["status"]

    def get_result(self, job_id: str) -> JobResult:
        """Get job result."""
        if job_id not in self._jobs:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error="Job not found"
            )

        job = self._jobs[job_id]
        status = self.get_status(job_id)  # Update status

        # Read output files
        stdout = None
        stderr = None
        if job["stdout_file"].exists():
            stdout = job["stdout_file"].read_text()
        if job["stderr_file"].exists():
            stderr = job["stderr_file"].read_text()

        return JobResult(
            job_id=job_id,
            status=status,
            output=stdout,
            error=stderr,
            exit_code=job.get("exit_code"),
            started_at=job.get("started_at"),
            finished_at=job.get("finished_at"),
            metadata={"name": job["name"], "command": " ".join(job["command"])}
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        process = job.get("process")

        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

            job["status"] = JobStatus.CANCELLED
            job["finished_at"] = datetime.now()
            return True

        return False

    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs."""
        if job_id not in self._jobs:
            return f"Job {job_id} not found"

        job = self._jobs[job_id]
        stdout_file = job["stdout_file"]
        stderr_file = job["stderr_file"]

        logs = []
        if stdout_file.exists():
            lines = stdout_file.read_text().splitlines()
            logs.append("=== STDOUT ===")
            logs.extend(lines[-tail:] if len(lines) > tail else lines)

        if stderr_file.exists():
            lines = stderr_file.read_text().splitlines()
            logs.append("\n=== STDERR ===")
            logs.extend(lines[-tail:] if len(lines) > tail else lines)

        return "\n".join(logs)

    def wait_for_completion(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 5
    ) -> JobResult:
        """Wait for job completion."""
        if job_id not in self._jobs:
            return JobResult(
                job_id=job_id,
                status=JobStatus.UNKNOWN,
                error="Job not found"
            )

        start_time = time.time()
        while True:
            status = self.get_status(job_id)

            if status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
                return self.get_result(job_id)

            if timeout and (time.time() - start_time) > timeout:
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.UNKNOWN,
                    error="Timeout waiting for job completion"
                )

            time.sleep(poll_interval)

    def cleanup(self, job_id: str) -> bool:
        """Clean up job resources."""
        if job_id not in self._jobs:
            return False

        job_dir = self._get_job_dir(job_id)
        if job_dir.exists():
            import shutil
            shutil.rmtree(job_dir)

        del self._jobs[job_id]
        return True
