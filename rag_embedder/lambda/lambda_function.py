"""
AWS Lambda function to trigger ECS tasks for rag_embedder worker operations.

Lambda Environment Variables:
    TASK_DEFINITION_ARN: ECS task definition ARN
    ECS_CLUSTER: ECS cluster name
    SUBNETS: Comma-separated subnet IDs
    SECURITY_GROUPS: Comma-separated security group IDs
    CONTAINER_NAME: Container name in task definition (default: rag-embedder)
    ASSIGN_PUBLIC_IP: ENABLED or DISABLED (default: DISABLED)

Task Definition Environment Variables (from SSM Parameter Store):
    QDRANT_HOST: from /rag/dev/qdrant-endpoint
    QDRANT_PORT: from /rag/dev/qdrant-port
    GITHUB_TOKEN: from /rag/dev/github-token
    API_TOKEN: from /rag/dev/api-token
"""

import json
import os
from datetime import datetime

try:
    import boto3
except ImportError:
    # boto3 is included in Lambda runtime but may not be available locally
    boto3 = None


def build_command(operation, params):
    """
    Build worker command array based on operation type.

    Args:
        operation: Operation name (upload_repo, upload_s3, etc.)
        params: Operation parameters dict

    Returns:
        List of command arguments

    Raises:
        ValueError: If operation is invalid or required params missing
    """
    # Empty base_cmd since ENTRYPOINT is already set in Dockerfile
    base_cmd = []

    if operation == "upload_repo":
        if not params.get("repo_url") or not params.get("collection"):
            raise ValueError("upload_repo requires 'repo_url' and 'collection'")

        # Note: GITHUB_TOKEN is provided via task definition environment variables
        return base_cmd + ["upload", "repo", params["repo_url"], params["collection"]]

    elif operation == "upload_s3":
        if not params.get("bucket") or not params.get("collection"):
            raise ValueError("upload_s3 requires 'bucket' and 'collection'")

        cmd = base_cmd + ["upload", "s3", params["bucket"], params["collection"]]
        if params.get("prefix"):
            cmd.extend(["--prefix", params["prefix"]])
        if params.get("endpoint"):
            cmd.extend(["--endpoint", params["endpoint"]])
        return cmd

    elif operation == "collection_create":
        if not params.get("collection") or not params.get("vector_size"):
            raise ValueError("collection_create requires 'collection' and 'vector_size'")

        cmd = base_cmd + [
            "collections",
            "create",
            params["collection"],
            "--vector-size",
            str(params["vector_size"])
        ]
        if params.get("embedding_model"):
            cmd.extend(["--embedding-model", params["embedding_model"]])
        return cmd

    elif operation == "collection_delete":
        if not params.get("collection"):
            raise ValueError("collection_delete requires 'collection'")

        return base_cmd + ["collections", "delete", params["collection"], "--yes"]

    elif operation == "collection_list":
        return base_cmd + ["collections", "list"]

    else:
        raise ValueError(f"Unknown operation: {operation}")


def lambda_handler(event, context):
    """
    Lambda handler to trigger ECS tasks for rag_embedder operations.

    Expected event format:
    {
        "operation": "upload_repo|upload_s3|collection_create|collection_delete|collection_list",
        "params": {
            "collection": "docs",
            "repo_url": "...",
            ...
        }
    }

    Returns:
        Dict with statusCode and body containing task info or error
    """
    try:
        # API Gateway (HTTP API) sends JSON in the body string for proxy integrations.
        if isinstance(event, dict) and "body" in event:
            body = event.get("body") or ""
            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "error": "Validation Error",
                        "message": "Invalid JSON body"
                    })
                }

        # Validate event structure
        if not isinstance(event, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Validation Error",
                    "message": "Event must be a JSON object"
                })
            }

        operation = event.get("operation")
        params = event.get("params", {})

        if not operation:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Validation Error",
                    "message": "Missing required field: 'operation'"
                })
            }

        # Build command
        try:
            command = build_command(operation, params)
        except ValueError as e:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Validation Error",
                    "message": str(e)
                })
            }

        # Get environment configuration
        task_definition_arn = os.getenv("TASK_DEFINITION_ARN")
        cluster = os.getenv("ECS_CLUSTER")
        subnets = [s.strip() for s in os.getenv("SUBNETS", "").split(",") if s.strip()]
        security_groups = [s.strip() for s in os.getenv("SECURITY_GROUPS", "").split(",") if s.strip()]
        container_name = os.getenv("CONTAINER_NAME", "rag-embedder")
        assign_public_ip = os.getenv("ASSIGN_PUBLIC_IP", "DISABLED")

        # Validate configuration
        if not task_definition_arn:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "TASK_DEFINITION_ARN environment variable not set"
                })
            }
        if not cluster:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "ECS_CLUSTER environment variable not set"
                })
            }
        if not subnets:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "SUBNETS environment variable not set"
                })
            }
        if not security_groups:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "SECURITY_GROUPS environment variable not set"
                })
            }

        # Initialize ECS client
        if boto3 is None:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "boto3 not available"
                })
            }
        ecs = boto3.client("ecs")

        # Run ECS task
        response = ecs.run_task(
            cluster=cluster,
            taskDefinition=task_definition_arn,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": assign_public_ip
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": container_name,
                        "command": command
                    }
                ]
            },
            tags=[
                {"key": "ManagedBy", "value": "Lambda"},
                {"key": "Operation", "value": operation}
            ]
        )

        # Check for failures
        if response.get("failures"):
            failure_reasons = [f["reason"] for f in response["failures"]]
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Task Execution Error",
                    "message": f"Failed to run task: {'; '.join(failure_reasons)}"
                })
            }

        # Extract task info
        task = response["tasks"][0]
        task_arn = task["taskArn"]
        task_id = task_arn.split("/")[-1]

        return {
            "statusCode": 202,
            "body": json.dumps({
                "message": f"Task triggered for operation '{operation}'",
                "task_arn": task_arn,
                "task_id": task_id,
                "status": task["lastStatus"],
                "created_at": task["createdAt"].isoformat(),
                "cluster": cluster,
                "command": " ".join(command)
            })
        }

    except Exception as e:
        # Catch-all for unexpected errors
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal Server Error",
                "message": str(e)
            })
        }
