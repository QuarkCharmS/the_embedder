# RAG Embedder Usage Guide

## Overview
One-off task system for processing documents and uploading them to Qdrant vector database. Triggered via HTTP API.

## Architecture
```
HTTP Request → API Gateway → Lambda → ECS Fargate Task → Qdrant
```

## Deployment

### 1. Deploy modules in order:
```bash
cd terragrunt/dev/rag-embedder
terragrunt apply

cd ../qdrant
terragrunt apply

cd ../rag-embedder-lambda
terragrunt apply
```

### 2. Get API endpoint:
```bash
terragrunt output run_url
```

## API Usage

### Endpoint
```
POST https://{api-id}.execute-api.us-east-1.amazonaws.com/run
```

### Request Format
```json
{
  "operation": "operation_name",
  "params": {
    // operation-specific parameters
  }
}
```

### Response
```json
{
  "statusCode": 202,
  "body": {
    "message": "Task triggered for operation 'operation_name'",
    "task_arn": "arn:aws:ecs:us-east-1:...:task/...",
    "task_id": "abc123..."
  }
}
```

## Available Operations

### 1. Upload Git Repository
Process and embed all files from a git repository.

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "upload_repo",
    "params": {
      "collection": "docs",
      "repo_url": "https://github.com/user/repo.git"
    }
  }'
```

### 2. Upload S3 Bucket
Process files from S3 bucket.

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "upload_s3",
    "params": {
      "collection": "docs",
      "bucket": "my-bucket",
      "prefix": "path/to/files/",
      "endpoint": "https://s3.amazonaws.com"
    }
  }'
```

**Note**: `prefix` and `endpoint` are optional.

### 3. Create Collection
Create a new Qdrant collection.

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "collection_create",
    "params": {
      "collection": "docs",
      "vector_size": 3072,
      "embedding_model": "text-embedding-3-large"
    }
  }'
```

### 4. Delete Collection
Delete a Qdrant collection.

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "collection_delete",
    "params": {
      "collection": "docs"
    }
  }'
```

### 5. List Collections
List all Qdrant collections.

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "collection_list",
    "params": {}
  }'
```

## Monitoring

### CloudWatch Logs
- **Lambda logs**: `/aws/lambda/dev-rag-embedder-trigger`
- **Task logs**: `/ecs/rag-embedder`

### ECS Console
Monitor task status using the returned `task_arn`:
```bash
aws ecs describe-tasks \
  --cluster qdrant-cluster \
  --tasks {task_id}
```

## Environment Variables (SSM)

The following SSM parameters must exist:
- `/rag/dev/qdrant-endpoint` - Qdrant host (e.g., qdrant.internal)
- `/rag/dev/qdrant-port` - Qdrant port (6333)
- `/rag/dev/github-token` - GitHub personal access token (for private repos)
- `/rag/dev/api-token` - Embedding API token

## Troubleshooting

### Task fails to start
- Check Lambda logs: `/aws/lambda/dev-rag-embedder-trigger`
- Verify IAM permissions (ecs:RunTask, iam:PassRole)
- Check task definition exists

### Task starts but fails
- Check task logs: `/ecs/rag-embedder`
- Verify SSM parameters exist and are accessible
- Check security groups allow Qdrant access (port 6333)

### API Gateway errors
- 403: Check Lambda permissions for API Gateway
- 500: Check Lambda execution role and code

## Example Workflow

```bash
# 1. Get API endpoint
export API_ENDPOINT=$(cd terragrunt/dev/rag-embedder-lambda && terragrunt output -raw run_url)

# 2. Create collection
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "collection_create",
    "params": {
      "collection": "my-docs",
      "vector_size": 3072,
      "embedding_model": "text-embedding-3-large"
    }
  }'

# 3. Upload repository
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "upload_repo",
    "params": {
      "collection": "my-docs",
      "repo_url": "https://github.com/myorg/docs.git"
    }
  }'

# 4. List collections to verify
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "collection_list",
    "params": {}
  }'
```

## Architecture Details

### Components
- **API Gateway**: HTTP API with POST /run endpoint
- **Lambda**: Triggers ECS tasks, passes operation parameters
- **ECS Fargate**: Runs rag-embedder container as one-off task
- **Qdrant**: Vector database (accessed via qdrant.internal:6333)

### Security
- API Gateway: Public endpoint (add authentication if needed)
- Lambda: IAM role with minimal ECS permissions
- ECS Task: Runs in private subnets, no public IP
- Qdrant: Internal only, accessed via NLB

### Costs
- API Gateway: Per request
- Lambda: Per invocation (minimal)
- ECS Fargate: Per task runtime (CPU/memory/duration)
- No always-on costs (everything is on-demand)
