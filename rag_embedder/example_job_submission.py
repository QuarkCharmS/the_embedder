"""
Example: How to submit jobs using the multi-environment runtime system.

This script demonstrates submitting different types of jobs
(upload, collection management) across different runtimes.
"""

import os
import sys
from pathlib import Path

# Ensure app module is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.jobs import UploadRepoJob, UploadFileJob, CollectionJob
from app.runtimes import get_runtime, JobStatus
from app.config import get_config, RuntimeBackend


def example_local_upload():
    """Example: Upload repository using local subprocess execution."""
    print("=" * 70)
    print("Example 1: Local Upload (Development)")
    print("=" * 70)

    # Configure for local execution
    os.environ["RUNTIME_BACKEND"] = "local"
    os.environ["QDRANT_HOST"] = "localhost"

    # Create job
    job = UploadRepoJob(
        job_name="upload-test-repo",
        repo_url="https://github.com/anthropics/anthropic-sdk-python.git",
        collection_name="anthropic_sdk",
        embedding_model="Qwen/Qwen3-Embedding-8B",
        api_token=os.getenv("API_TOKEN", "your-api-token")
    )

    # Get runtime
    runtime = get_runtime()
    print(f"Runtime: {type(runtime).__name__}")

    # Submit job
    print(f"\nSubmitting job: {job.job_name}")
    print(f"Repository: {job.repo_url}")
    print(f"Collection: {job.collection_name}")

    job_def = job.to_definition()
    job_id = runtime.submit_job(
        job_name=job_def.name,
        command=job_def.command,
        env=job_def.env,
        resources=job_def.resources,
        image=job_def.image
    )

    print(f"Job ID: {job_id}")

    # Monitor job
    print("\nMonitoring job...")
    result = runtime.wait_for_completion(job_id, timeout=3600, poll_interval=5)

    print(f"\nJob Status: {result.status.value}")
    if result.status == JobStatus.SUCCEEDED:
        print("✓ Job completed successfully!")
    else:
        print(f"✗ Job failed: {result.error}")
        print("\nLogs:")
        print(runtime.get_logs(job_id))


def example_docker_collection():
    """Example: Create collection using Docker container."""
    print("\n" + "=" * 70)
    print("Example 2: Docker Collection Create (Testing)")
    print("=" * 70)

    # Configure for Docker
    os.environ["RUNTIME_BACKEND"] = "docker"
    os.environ["DOCKER_NETWORK"] = "rag-network"
    os.environ["WORKER_IMAGE"] = "rag-worker:latest"

    # Create collection job (lightweight)
    job = CollectionJob(
        job_name="create-test-collection",
        operation="create",
        collection_name="test_collection",
        dimension=1536
    )

    runtime = get_runtime()
    print(f"Runtime: {type(runtime).__name__}")

    print(f"\nCreating collection: {job.collection_name}")
    print(f"Dimension: {job.dimension}")

    job_def = job.to_definition()
    job_id = runtime.submit_job(
        job_name=job_def.name,
        command=job_def.command,
        env=job_def.env,
        resources=job_def.resources,
        image=job_def.image
    )

    print(f"Job ID: {job_id}")

    # Wait for completion
    result = runtime.wait_for_completion(job_id, timeout=300)

    print(f"\nStatus: {result.status.value}")
    if result.status == JobStatus.SUCCEEDED:
        print("✓ Collection created successfully!")
    else:
        print(f"✗ Failed: {result.error}")


def example_kubernetes_upload():
    """Example: Upload repository using Kubernetes Job."""
    print("\n" + "=" * 70)
    print("Example 3: Kubernetes Upload (Production)")
    print("=" * 70)

    # Configure for Kubernetes
    os.environ["RUNTIME_BACKEND"] = "kubernetes"
    os.environ["K8S_NAMESPACE"] = "default"
    os.environ["WORKER_IMAGE"] = "your-registry/rag-worker:latest"
    os.environ["QDRANT_HOST"] = "qdrant-service"

    job = UploadRepoJob(
        job_name="upload-prod-docs",
        repo_url="https://github.com/company/docs.git",
        collection_name="company_docs",
        embedding_model="Qwen/Qwen3-Embedding-8B",
        api_token=os.getenv("API_TOKEN", "your-api-token")
    )

    runtime = get_runtime()
    print(f"Runtime: {type(runtime).__name__}")

    print(f"\nSubmitting to Kubernetes...")
    print(f"Namespace: {os.getenv('K8S_NAMESPACE')}")

    job_def = job.to_definition()
    job_id = runtime.submit_job(
        job_name=job_def.name,
        command=job_def.command,
        env=job_def.env,
        resources=job_def.resources,
        image=job_def.image
    )

    print(f"Kubernetes Job created: {job_id}")
    print(f"\nMonitor with:")
    print(f"  kubectl get job {job_id} -n {os.getenv('K8S_NAMESPACE')}")
    print(f"  kubectl logs -f job/{job_id} -n {os.getenv('K8S_NAMESPACE')}")

    # For production, you might not wait synchronously
    # Instead, check status periodically or use webhooks
    print("\nJob submitted successfully!")


def example_aws_batch_upload():
    """Example: Upload repository using AWS Batch."""
    print("\n" + "=" * 70)
    print("Example 4: AWS Batch Upload (Cloud Production)")
    print("=" * 70)

    # Configure for AWS Batch
    os.environ["RUNTIME_BACKEND"] = "aws_batch"
    os.environ["AWS_BATCH_JOB_QUEUE"] = "rag-processing-queue"
    os.environ["AWS_BATCH_JOB_DEFINITION"] = "rag-worker:1"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["QDRANT_HOST"] = "qdrant.internal.company.com"

    job = UploadRepoJob(
        job_name="upload-large-repo",
        repo_url="https://github.com/company/large-repo.git",
        collection_name="large_repo",
        embedding_model="Qwen/Qwen3-Embedding-8B",
        api_token=os.getenv("API_TOKEN", "your-api-token")
    )

    runtime = get_runtime()
    print(f"Runtime: {type(runtime).__name__}")

    print(f"\nSubmitting to AWS Batch...")
    print(f"Job Queue: {os.getenv('AWS_BATCH_JOB_QUEUE')}")
    print(f"Region: {os.getenv('AWS_REGION')}")

    job_def = job.to_definition()
    job_id = runtime.submit_job(
        job_name=job_def.name,
        command=job_def.command,
        env=job_def.env,
        resources=job_def.resources
    )

    print(f"\nAWS Batch Job ID: {job_id}")
    print(f"\nMonitor with:")
    print(f"  aws batch describe-jobs --jobs {job_id}")
    print(f"\nView logs in CloudWatch Logs")

    print("\nJob submitted successfully!")


def example_submit_multiple_jobs():
    """Example: Submit multiple jobs in parallel."""
    print("\n" + "=" * 70)
    print("Example 5: Multiple Jobs in Parallel")
    print("=" * 70)

    os.environ["RUNTIME_BACKEND"] = "local"

    jobs_to_submit = [
        CollectionJob("create-col1", "create", "collection1", 1536),
        CollectionJob("create-col2", "create", "collection2", 768),
        CollectionJob("create-col3", "create", "collection3", 1024),
    ]

    runtime = get_runtime()
    job_ids = []

    print("Submitting jobs...")
    for job in jobs_to_submit:
        job_def = job.to_definition()
        job_id = runtime.submit_job(
            job_name=job_def.name,
            command=job_def.command,
            env=job_def.env,
            resources=job_def.resources
        )
        job_ids.append((job_id, job.collection_name))
        print(f"  Submitted: {job.collection_name} -> {job_id}")

    print("\nWaiting for all jobs to complete...")
    for job_id, collection_name in job_ids:
        result = runtime.wait_for_completion(job_id, timeout=300)
        status_icon = "✓" if result.status == JobStatus.SUCCEEDED else "✗"
        print(f"  {status_icon} {collection_name}: {result.status.value}")


def example_check_config():
    """Example: Check current configuration."""
    print("\n" + "=" * 70)
    print("Current Configuration")
    print("=" * 70)

    config = get_config()

    print(f"\nRuntime Backend: {config.backend.value}")
    print(f"Worker Image: {config.worker_image}")
    print(f"Qdrant: {config.qdrant_host}:{config.qdrant_port}")

    if config.backend == RuntimeBackend.DOCKER:
        print(f"Docker Network: {config.docker_network}")

    elif config.backend == RuntimeBackend.KUBERNETES:
        print(f"K8s Namespace: {config.k8s_namespace}")
        if config.k8s_service_account:
            print(f"Service Account: {config.k8s_service_account}")

    elif config.backend == RuntimeBackend.AWS_BATCH:
        print(f"AWS Region: {config.aws_region}")
        print(f"Job Queue: {config.aws_batch_job_queue}")
        print(f"Job Definition: {config.aws_batch_job_definition}")


def main():
    """Run examples based on user selection."""
    print("\nRAG Job Submission Examples")
    print("=" * 70)

    if len(sys.argv) > 1:
        example = sys.argv[1]
    else:
        print("\nAvailable examples:")
        print("  1 - Local upload (development)")
        print("  2 - Docker collection create (testing)")
        print("  3 - Kubernetes upload (production)")
        print("  4 - AWS Batch upload (cloud)")
        print("  5 - Multiple jobs in parallel")
        print("  config - Show current configuration")
        print("\nUsage: python example_job_submission.py <example_number>")
        example = input("\nSelect example (1-5, config): ").strip()

    if example == "1":
        example_local_upload()
    elif example == "2":
        example_docker_collection()
    elif example == "3":
        example_kubernetes_upload()
    elif example == "4":
        example_aws_batch_upload()
    elif example == "5":
        example_submit_multiple_jobs()
    elif example == "config":
        example_check_config()
    else:
        print(f"Unknown example: {example}")
        sys.exit(1)


if __name__ == "__main__":
    main()
