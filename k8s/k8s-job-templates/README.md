# RAG Embedder - Kubernetes Job Templates

One-time run job templates for RAG Embedder operations on Kubernetes.

## Features

- **Secret-based configuration**: No hardcoded credentials in manifests
- **Auto-generated unique names**: Each job run gets a unique name via `generateName`
- **Auto-cleanup**: Jobs automatically delete 5 minutes after completion
- **Simple .env mounting**: Use the same .env pattern as local development

## Quick Start

### 1. Create the Secret

First, copy and edit the .env template:

```bash
cd k8s-job-templates
cp .env.template .env
# Edit .env with your actual values (API_TOKEN, etc.)
```

Create the Kubernetes Secret:

```bash
kubectl create secret generic rag-embedder-env --from-file=.env
```

### 2. Run Jobs

**Create a collection:**
```bash
# Edit COLLECTION_NAME, VECTOR_SIZE, EMBEDDING_MODEL if needed
kubectl apply -f create-collection-job.yaml
```

**Upload a repository:**
```bash
# Edit REPO_URL and COLLECTION_NAME if needed
kubectl apply -f upload-repo-job.yaml
```

**Upload from S3:**
```bash
# Edit BUCKET_NAME, PREFIX, and COLLECTION_NAME if needed
kubectl apply -f upload-s3-job.yaml
```

**Upload a file:**
```bash
# Requires additional volume setup - see file comments
kubectl apply -f upload-file-job.yaml
```

### 3. Monitor Jobs

```bash
# List all jobs
kubectl get jobs

# Watch job progress
kubectl get jobs -w

# Get logs (replace <job-name> with actual name from get jobs)
kubectl logs job/<job-name>

# Follow logs
kubectl logs -f job/<job-name>
```

## Configuration

### Secret Management

The `rag-embedder-env` Secret contains your .env file with sensitive configuration:
- `QDRANT_HOST` and `QDRANT_PORT`
- `API_TOKEN` (your embedding provider API key)
- `MODEL_NAME` (default model)
- `GITHUB_TOKEN` (for private repos)
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (for S3 uploads)

To update the secret:
```bash
kubectl delete secret rag-embedder-env
kubectl create secret generic rag-embedder-env --from-file=.env
```

### Job Parameters

Each job template has environment variables you can customize:

**create-collection-job.yaml:**
- `COLLECTION_NAME`: Name of the collection to create
- `VECTOR_SIZE`: Embedding dimensions (e.g., 4096, 1536)
- `EMBEDDING_MODEL`: Model to use for embeddings

**upload-repo-job.yaml:**
- `REPO_URL`: Git repository URL to clone and process
- `COLLECTION_NAME`: Target collection for embeddings

**upload-s3-job.yaml:**
- `BUCKET_NAME`: S3 bucket name
- `PREFIX`: S3 prefix/folder (optional, e.g., "documents/")
- `COLLECTION_NAME`: Target collection for embeddings
- `AWS_REGION`: AWS region (default: us-east-1)

**upload-file-job.yaml:**
- `FILE_PATH`: Path to file/directory to upload
- `COLLECTION_NAME`: Target collection for embeddings

### Auto-Cleanup

Jobs are configured with `ttlSecondsAfterFinished: 300` (5 minutes).

To change cleanup time, edit the `ttlSecondsAfterFinished` value:
- `300` = 5 minutes
- `600` = 10 minutes
- `0` = delete immediately after completion

To keep jobs indefinitely, remove the `ttlSecondsAfterFinished` field entirely.

## Unique Job Names

Jobs use `generateName` instead of `name`, so Kubernetes appends a random suffix:
- `rag-create-collection-abc123`
- `rag-upload-repo-xyz789`

This allows you to run the same job template multiple times without conflicts.

## Troubleshooting

**Job fails immediately:**
- Check if the `rag-embedder-env` Secret exists: `kubectl get secret rag-embedder-env`
- Verify your .env file has valid API_TOKEN and other required values
- Check job logs: `kubectl logs job/<job-name>`

**Can't find job:**
- Jobs auto-delete after 5 minutes. Check recently completed jobs:
  ```bash
  kubectl get events --sort-by='.lastTimestamp'
  ```

**Secret not mounting:**
- Verify secret exists in the same namespace as the job
- Check the secret contains the .env key: `kubectl describe secret rag-embedder-env`

## Advanced Usage

### Run with Different Namespace

Edit the job YAML and change:
```yaml
metadata:
  namespace: my-namespace
```

Ensure the Secret exists in that namespace.

### Custom Image

To use a different image version or registry:
```yaml
containers:
  - name: rag-cli
    image: my-registry/rag_embedder:v2.0
```

### Add Resource Limits

Add resource constraints:
```yaml
containers:
  - name: rag-cli
    resources:
      limits:
        cpu: "2"
        memory: "4Gi"
      requests:
        cpu: "1"
        memory: "2Gi"
```

## Security Notes

- Never commit your `.env` file to version control
- The Secret is mounted read-only in the container
- Jobs run with default pod security context
- Consider using a dedicated namespace for isolation
- For production, use RBAC to restrict Secret access

## Cleanup

Delete all jobs manually:
```bash
kubectl delete jobs -l managed-by=rag-embedder
```

Or wait for auto-cleanup after 5 minutes.

Delete the Secret (when no longer needed):
```bash
kubectl delete secret rag-embedder-env
```
