# Multi-Environment Job Runtime Architecture

Complete architecture for running RAG jobs across multiple execution environments (local, Docker, Kubernetes, AWS) from a single codebase.

---

## Overview

This system separates **WHAT** to execute (Job definitions) from **HOW** to execute (Runtime implementations), allowing the same job to run in different environments based on configuration.

### Key Concepts

- **Job**: Defines what operation to perform (upload repo, create collection, etc.)
- **Runtime**: Defines how to execute the job (local process, Docker container, K8s Job, AWS Batch)
- **Factory**: Automatically selects the appropriate runtime based on environment configuration

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                          CLI / API                           │
│                    (Job Submission Layer)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ creates
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      Job Definition                          │
│  (UploadRepoJob, CollectionJob, UploadFileJob)             │
│  - Command to execute                                        │
│  - Environment variables                                     │
│  - Resource requirements                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ submit_job()
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                     Runtime Factory                          │
│          (Selects runtime based on config)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ↓                  ↓                  ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Local     │  │   Docker    │  │ Kubernetes  │  ...
│  Runtime    │  │  Runtime    │  │  Runtime    │
└─────────────┘  └─────────────┘  └─────────────┘
        │                  │                  │
        ↓                  ↓                  ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Subprocess  │  │  Container  │  │   K8s Job   │
└─────────────┘  └─────────────┘  └─────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                         Worker                               │
│              (app/worker.py - actual execution)              │
│  - Imports handlers                                          │
│  - Executes upload/collection operations                     │
│  - Runs inside container or subprocess                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
app/
├── config.py                   # Configuration management
├── worker.py                   # Worker entry point (runs inside containers)
│
├── jobs/                       # Job definitions (WHAT to execute)
│   ├── __init__.py
│   ├── base.py                # Job base class
│   ├── upload_repo_job.py     # Upload repository job
│   ├── upload_file_job.py     # Upload file/archive job
│   └── collection_job.py      # Collection management job
│
├── runtimes/                   # Runtime implementations (HOW to execute)
│   ├── __init__.py
│   ├── base.py                # JobRuntime ABC + JobStatus/JobResult
│   ├── local.py               # Local subprocess execution
│   ├── docker.py              # Docker SDK execution
│   ├── kubernetes.py          # Kubernetes Jobs
│   ├── aws_batch.py           # AWS Batch
│   └── factory.py             # Runtime factory/selector
│
└── [existing files...]
    ├── handlers.py            # Execution logic (used by worker)
    ├── qdrant_manager.py      # Qdrant operations
    └── ...
```

---

## Core Components

### 1. Job Definition (`app/jobs/base.py`)

Defines **WHAT** to execute:

```python
from app.jobs import UploadRepoJob

# Create job definition
job = UploadRepoJob(
    job_name="upload-myrepo",
    repo_url="https://github.com/user/repo.git",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="sk-..."
)

# Job knows its requirements
command = job.get_command()        # ["python", "-m", "app.worker", "upload_repo", ...]
env = job.get_environment()        # {"QDRANT_HOST": "...", "MODEL_NAME": "...", ...}
resources = job.get_resources()    # JobResources(cpu="2", memory="4Gi", timeout=3600)
```

### 2. Runtime (`app/runtimes/base.py`)

Defines **HOW** to execute:

```python
from app.runtimes import get_runtime

# Get runtime (auto-selected based on RUNTIME_BACKEND env var)
runtime = get_runtime()

# Submit job
job_id = runtime.submit_job(
    job_name=job.job_name,
    command=job.get_command(),
    env=job.get_environment(),
    resources=job.get_resources(),
    image=job.get_image()
)

# Monitor job
status = runtime.get_status(job_id)
result = runtime.wait_for_completion(job_id)
logs = runtime.get_logs(job_id)
```

### 3. Runtime Factory (`app/runtimes/factory.py`)

Automatically selects runtime based on configuration:

```python
from app.runtimes import RuntimeFactory
from app.config import Config, RuntimeBackend

# Configure runtime
config = Config(backend=RuntimeBackend.AWS_BATCH)

# Factory creates appropriate runtime
runtime = RuntimeFactory.create_runtime(config)
# Returns AWSBatchRuntime instance
```

### 4. Worker (`app/worker.py`)

Entry point that runs **inside** containers/subprocesses:

```bash
# This is what gets executed
python -m app.worker upload_repo https://github.com/user/repo.git collection_name
```

The worker imports handlers and executes the actual work.

---

## Configuration

### Environment Variables

```bash
# Runtime selection
RUNTIME_BACKEND=local|docker|kubernetes|aws_batch

# Worker image (for containerized runtimes)
WORKER_IMAGE=rag-worker:latest

# Qdrant connection
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Docker configuration
DOCKER_NETWORK=rag-network

# Kubernetes configuration
K8S_NAMESPACE=default
K8S_SERVICE_ACCOUNT=rag-worker
K8S_IMAGE_PULL_SECRETS=docker-registry-secret

# AWS configuration
AWS_REGION=us-east-1
AWS_BATCH_JOB_QUEUE=rag-processing-queue
AWS_BATCH_JOB_DEFINITION=rag-worker:1

# Job defaults
JOB_TIMEOUT=3600
MAX_RETRIES=3
```

---

## Usage Examples

### Example 1: Local Development

```python
import os
from app.jobs import UploadRepoJob
from app.runtimes import get_runtime

# Configure for local execution
os.environ["RUNTIME_BACKEND"] = "local"
os.environ["QDRANT_HOST"] = "localhost"

# Create job
job = UploadRepoJob(
    job_name="upload-myrepo",
    repo_url="https://github.com/user/repo.git",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="sk-..."
)

# Get runtime (will be LocalRuntime)
runtime = get_runtime()

# Submit and wait
job_id = runtime.submit_job(
    job_name=job.job_name,
    command=job.get_command(),
    env=job.get_environment(),
    resources=job.get_resources()
)

print(f"Job submitted: {job_id}")

# Wait for completion
result = runtime.wait_for_completion(job_id, timeout=3600)

if result.status == JobStatus.SUCCEEDED:
    print("Job completed successfully!")
else:
    print(f"Job failed: {result.error}")
```

### Example 2: Docker Execution

```python
import os
from app.jobs import CollectionJob
from app.runtimes import get_runtime

# Configure for Docker
os.environ["RUNTIME_BACKEND"] = "docker"
os.environ["DOCKER_NETWORK"] = "rag-network"
os.environ["WORKER_IMAGE"] = "rag-worker:latest"

# Create lightweight collection job
job = CollectionJob(
    job_name="create-collection",
    operation="create",
    collection_name="my_collection",
    dimension=1536
)

# Submit to Docker
runtime = get_runtime()
job_id = runtime.submit_job(
    job_name=job.job_name,
    command=job.get_command(),
    env=job.get_environment(),
    resources=job.get_resources(),
    image=job.get_image()
)

# Stream logs
logs = runtime.get_logs(job_id, tail=50)
print(logs)
```

### Example 3: Kubernetes Production

```python
import os
from app.jobs import UploadRepoJob
from app.runtimes import get_runtime

# Configure for Kubernetes
os.environ["RUNTIME_BACKEND"] = "kubernetes"
os.environ["K8S_NAMESPACE"] = "production"
os.environ["WORKER_IMAGE"] = "your-registry/rag-worker:v1.0.0"
os.environ["QDRANT_HOST"] = "qdrant-service.production.svc.cluster.local"

# Create job
job = UploadRepoJob(
    job_name="upload-docs",
    repo_url="https://github.com/company/docs.git",
    collection_name="company_docs",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token=os.getenv("API_TOKEN")
)

# Submit to K8s
runtime = get_runtime()
job_id = runtime.submit_job(
    job_name=job.job_name,
    command=job.get_command(),
    env=job.get_environment(),
    resources=job.get_resources(),
    image=job.get_image()
)

print(f"Kubernetes Job created: {job_id}")
print(f"Monitor with: kubectl get job {job_id} -n production")
```

### Example 4: AWS Batch at Scale

```python
import os
from app.jobs import UploadRepoJob
from app.runtimes import get_runtime

# Configure for AWS Batch
os.environ["RUNTIME_BACKEND"] = "aws_batch"
os.environ["AWS_BATCH_JOB_QUEUE"] = "rag-processing-queue"
os.environ["AWS_BATCH_JOB_DEFINITION"] = "rag-worker:1"
os.environ["QDRANT_HOST"] = "qdrant.internal.company.com"

# Create job
job = UploadRepoJob(
    job_name="upload-large-repo",
    repo_url="https://github.com/company/large-repo.git",
    collection_name="large_repo",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token=os.getenv("API_TOKEN")
)

# Submit to AWS Batch
runtime = get_runtime()
job_id = runtime.submit_job(
    job_name=job.job_name,
    command=job.get_command(),
    env=job.get_environment(),
    resources=job.get_resources()
)

print(f"AWS Batch job submitted: {job_id}")

# Optionally wait (async recommended for long jobs)
# result = runtime.wait_for_completion(job_id, timeout=7200)
```

---

## Job Types and Resource Requirements

| Job Type | CPU | Memory | Timeout | Use Case |
|----------|-----|--------|---------|----------|
| **CollectionJob** | 0.25 | 256Mi | 5 min | Create/delete/list collections (lightweight) |
| **UploadFileJob** | 1 | 2Gi | 30 min | Upload single files or small archives |
| **UploadRepoJob** | 2 | 4Gi | 1 hour | Upload git repositories (heavy processing) |

---

## Runtime Comparison

| Runtime | Startup | Cost | Use Case | Pros | Cons |
|---------|---------|------|----------|------|------|
| **Local** | Instant | Free | Development | Fast, simple, no overhead | No isolation, limited resources |
| **Docker** | 1-2s | Low | Local testing | Good isolation, portable | Requires Docker daemon |
| **Kubernetes** | 30-60s | Medium | Production | Auto-scaling, orchestration | Complex setup, slower startup |
| **AWS Batch** | 1-2 min | Low (pay per use) | Cloud production | Serverless, scales to zero | Cold start delay |

---

## Extending the System

### Adding a New Job Type

1. Create job class in `app/jobs/`:

```python
from app.jobs.base import Job
from app.runtimes.base import JobResources

class MyCustomJob(Job):
    def __init__(self, job_name: str, ...):
        super().__init__(job_name)
        # ... store parameters

    def get_operation_name(self) -> str:
        return "my_custom_operation"

    def get_command(self) -> List[str]:
        return ["python", "-m", "app.worker", "my_custom_operation", ...]

    def get_environment(self) -> Dict[str, str]:
        return {"VAR1": "value1", ...}

    def get_resources(self) -> JobResources:
        return JobResources(cpu="1", memory="1Gi", timeout=600)
```

2. Add handler in `app/worker.py`:

```python
def my_custom_operation(arg1, arg2):
    # Implementation
    print(f"Executing custom operation with {arg1}, {arg2}")
    # ... do work ...
```

### Adding a New Runtime

1. Create runtime class in `app/runtimes/`:

```python
from app.runtimes.base import JobRuntime, JobStatus, JobResult

class MyCustomRuntime(JobRuntime):
    def submit_job(self, ...):
        # Implementation
        pass

    def get_status(self, job_id: str) -> JobStatus:
        # Implementation
        pass

    # ... implement all abstract methods
```

2. Register in factory (`app/runtimes/factory.py`):

```python
elif backend == RuntimeBackend.MY_CUSTOM:
    return MyCustomRuntime(...)
```

---

## Best Practices

### 1. Job Design

- **Keep jobs focused**: One job = one operation
- **Make jobs idempotent**: Safe to retry on failure
- **Pass minimal data**: Use references (URLs, paths) not large payloads

### 2. Resource Sizing

- **Profile your workloads**: Measure actual resource usage
- **Set appropriate timeouts**: Prevent hung jobs
- **Use appropriate instance types**: Match job requirements to runtime

### 3. Error Handling

```python
try:
    result = runtime.wait_for_completion(job_id, timeout=3600)

    if result.status == JobStatus.SUCCEEDED:
        print("Success!")
    elif result.status == JobStatus.FAILED:
        print(f"Failed: {result.error}")
        print(f"Logs:\n{runtime.get_logs(job_id)}")
except Exception as e:
    print(f"Error: {e}")
    runtime.cancel_job(job_id)
```

### 4. Monitoring

- **Track job IDs**: Store in database for auditing
- **Collect metrics**: Job duration, success rate, resource usage
- **Set up alerts**: Failed jobs, timeouts, resource exhaustion

---

## Development Workflow

### Local Development

```bash
# Set local runtime
export RUNTIME_BACKEND=local
export QDRANT_HOST=localhost

# Run directly
python -m app.worker upload_repo https://github.com/user/repo.git collection
```

### Testing with Docker

```bash
# Build worker image
docker build -f Dockerfile -t rag-worker:latest .

# Set Docker runtime
export RUNTIME_BACKEND=docker
export WORKER_IMAGE=rag-worker:latest
export DOCKER_NETWORK=rag-network

# Submit job via Python
python submit_job.py
```

### Deploying to Production

```bash
# Build and push image
docker build -f Dockerfile -t your-registry/rag-worker:v1.0.0 .
docker push your-registry/rag-worker:v1.0.0

# Configure for AWS Batch
export RUNTIME_BACKEND=aws_batch
export AWS_BATCH_JOB_QUEUE=rag-processing
export AWS_BATCH_JOB_DEFINITION=rag-worker:1

# Submit production job
python submit_job.py
```

---

## Troubleshooting

### Job stuck in PENDING

- **Local**: Check if subprocess started
- **Docker**: Check if image exists (`docker images`)
- **K8s**: Check pod status (`kubectl get pods`)
- **AWS**: Check job queue and compute environment

### Job fails immediately

- Check logs: `runtime.get_logs(job_id)`
- Verify environment variables are set
- Check resource availability
- Verify image exists and is accessible

### Cannot connect to Qdrant

- Verify `QDRANT_HOST` and `QDRANT_PORT`
- Check network connectivity
- For Docker: ensure network is correct
- For K8s: verify service DNS
- For AWS: check security groups and VPC configuration

---

## Summary

This architecture provides:

✅ **Single codebase** for all environments
✅ **Environment-agnostic** job definitions
✅ **Automatic runtime selection** based on config
✅ **Production-ready** with proper abstraction
✅ **Extensible** - easy to add new jobs and runtimes
✅ **Type-safe** with clear interfaces
✅ **Testable** - can test jobs locally

Perfect for large-scale production deployments where you need flexibility in how jobs are executed while maintaining a clean, maintainable codebase.
