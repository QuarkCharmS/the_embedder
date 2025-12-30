# RAG Embedder Lambda Function

AWS Lambda function that triggers ECS Fargate tasks for rag_embedder worker operations.

## Deployment

### 1. Package the Lambda

```bash
cd lambda
zip lambda_function.zip lambda_function.py
```

### 2. Create IAM Role

Create an execution role with this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:RunTask",
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeClusters"
      ],
      "Resource": [
        "arn:aws:ecs:us-east-1:ACCOUNT_ID:task-definition/rag-embedder:*",
        "arn:aws:ecs:us-east-1:ACCOUNT_ID:cluster/qdrant-cluster"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::ACCOUNT_ID:role/*ecs-task-exec*",
        "arn:aws:iam::ACCOUNT_ID:role/*ecs-task-role*"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ecs-tasks.amazonaws.com"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/lambda/*"
    }
  ]
}
```

### 3. Deploy Lambda

```bash
aws lambda create-function \
  --function-name rag-embedder-trigger \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-ecs-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{
    TASK_DEFINITION_ARN=arn:aws:ecs:us-east-1:ACCOUNT_ID:task-definition/rag-embedder:1,
    ECS_CLUSTER=qdrant-cluster,
    SUBNETS=subnet-xxx,subnet-yyy,
    SECURITY_GROUPS=sg-xxx,
    CONTAINER_NAME=rag-embedder,
    ASSIGN_PUBLIC_IP=DISABLED
  }"
```

Or update existing:

```bash
aws lambda update-function-code \
  --function-name rag-embedder-trigger \
  --zip-file fileb://lambda_function.zip
```

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TASK_DEFINITION_ARN` | Yes | ECS task definition ARN | `arn:aws:ecs:us-east-1:123456789:task-definition/rag-embedder:1` |
| `ECS_CLUSTER` | Yes | ECS cluster name | `qdrant-cluster` |
| `SUBNETS` | Yes | Comma-separated subnet IDs | `subnet-abc123,subnet-def456` |
| `SECURITY_GROUPS` | Yes | Comma-separated security group IDs | `sg-abc123` |
| `CONTAINER_NAME` | No | Container name (default: rag-embedder) | `rag-embedder` |
| `ASSIGN_PUBLIC_IP` | No | Assign public IP (default: DISABLED) | `DISABLED` |

## Task Definition Environment Variables

The ECS task definition should include these environment variables (from SSM Parameter Store):

| Environment Variable | SSM Parameter | Description |
|---------------------|---------------|-------------|
| `QDRANT_HOST` | `/rag/dev/qdrant-endpoint` | Qdrant server hostname |
| `QDRANT_PORT` | `/rag/dev/qdrant-port` | Qdrant server port |
| `GITHUB_TOKEN` | `/rag/dev/github-token` | GitHub personal access token for private repos |
| `API_TOKEN` | `/rag/dev/api-token` | API token for embedding service |

These are configured at the task definition level, not passed as Lambda parameters.

## Usage

### Upload Repository

```bash
aws lambda invoke \
  --function-name rag-embedder-trigger \
  --payload '{"operation":"upload_repo","params":{"repo_url":"https://github.com/user/repo.git","collection":"docs"}}' \
  response.json

cat response.json
```

### Upload from S3

```bash
aws lambda invoke \
  --function-name rag-embedder-trigger \
  --payload '{"operation":"upload_s3","params":{"bucket":"my-bucket","collection":"docs","prefix":"documents/"}}' \
  response.json
```

### Create Collection

```bash
aws lambda invoke \
  --function-name rag-embedder-trigger \
  --payload '{"operation":"collection_create","params":{"collection":"embeddings","vector_size":3072}}' \
  response.json
```

### Delete Collection

```bash
aws lambda invoke \
  --function-name rag-embedder-trigger \
  --payload '{"operation":"collection_delete","params":{"collection":"old-collection"}}' \
  response.json
```

### List Collections

```bash
aws lambda invoke \
  --function-name rag-embedder-trigger \
  --payload '{"operation":"collection_list","params":{}}' \
  response.json
```

## Payload Format

### upload_repo
```json
{
  "operation": "upload_repo",
  "params": {
    "repo_url": "https://github.com/org/repo.git",
    "collection": "docs"
  }
}
```
**Note**: GitHub token for private repos is provided via task definition environment variables (`GITHUB_TOKEN` from SSM `/rag/dev/github-token`)

### upload_s3
```json
{
  "operation": "upload_s3",
  "params": {
    "bucket": "my-bucket",
    "collection": "docs",
    "prefix": "path/",      // optional
    "endpoint": "https://s3.custom.com"  // optional
  }
}
```

### collection_create
```json
{
  "operation": "collection_create",
  "params": {
    "collection": "embeddings",
    "vector_size": 3072
  }
}
```

### collection_delete
```json
{
  "operation": "collection_delete",
  "params": {
    "collection": "old-collection"
  }
}
```

### collection_list
```json
{
  "operation": "collection_list",
  "params": {}
}
```

## Response Format

### Success (202 Accepted)
```json
{
  "statusCode": 202,
  "body": {
    "message": "Task triggered for operation 'upload_repo'",
    "task_arn": "arn:aws:ecs:us-east-1:123456789:task/qdrant-cluster/abc123",
    "task_id": "abc123",
    "status": "PROVISIONING",
    "created_at": "2025-12-21T12:00:00Z",
    "cluster": "qdrant-cluster",
    "command": "python -m app.worker upload_repo https://github.com/user/repo.git docs"
  }
}
```

### Error (400/500)
```json
{
  "statusCode": 400,
  "body": {
    "error": "Validation Error",
    "message": "upload_repo requires 'repo_url' and 'collection'"
  }
}
```

## Monitoring

View Lambda logs:
```bash
aws logs tail /aws/lambda/rag-embedder-trigger --follow
```

View ECS task logs:
```bash
aws logs tail /ecs/rag-embedder --follow
```

Check task status:
```bash
aws ecs describe-tasks \
  --cluster qdrant-cluster \
  --tasks TASK_ID
```
