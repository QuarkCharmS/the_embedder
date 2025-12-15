"""
Container worker entry point for executing RAG operations.

Provides lightweight CLI for Docker/Kubernetes execution without Click dependency.

Operations: upload_repo, upload_file, upload_archive, upload_s3, collection_create,
collection_delete, collection_list

See ARCHITECTURE.md for detailed flow and logic.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_env_config():
    """Get common environment configuration."""
    return {
        'qdrant_host': os.getenv("QDRANT_HOST", "localhost"),
        'qdrant_port': int(os.getenv("QDRANT_PORT", "6333")),
        'embedding_model': os.getenv("MODEL_NAME"),
        'api_token': os.getenv("API_TOKEN")
    }


def upload_repo(repo_url: str, collection_name: str, git_token: str = None):
    """Execute repository upload."""
    from app.handlers import RepoHandler

    config = _get_env_config()
    if not config['embedding_model'] or not config['api_token']:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    github_token = git_token or os.getenv("GITHUB_TOKEN")

    print(f"Uploading repository: {repo_url}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {config['embedding_model']}")

    handler = RepoHandler()
    handler.handle(
        git_url=repo_url,
        collection_name=collection_name,
        embedding_model=config['embedding_model'],
        api_token=config['api_token'],
        git_token=github_token,
        debug_level="NONE"
    )

    print("Repository upload completed successfully")


def upload_file(file_path: str, collection_name: str):
    """Execute file upload."""
    from app.handlers import FileHandler

    config = _get_env_config()
    if not config['embedding_model'] or not config['api_token']:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    print(f"Uploading file: {file_path}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {config['embedding_model']}")

    FileHandler.handle(
        file_path=file_path,
        collection_name=collection_name,
        embedding_model=config['embedding_model'],
        api_token=config['api_token'],
        debug_level="NONE"
    )

    print("File upload completed successfully")


def upload_archive(archive_path: str, collection_name: str):
    """Execute archive upload."""
    from app.handlers import ArchiveHandler

    config = _get_env_config()
    if not config['embedding_model'] or not config['api_token']:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    print(f"Uploading archive: {archive_path}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {config['embedding_model']}")

    handler = ArchiveHandler()
    handler.handle(
        archive_path=archive_path,
        collection_name=collection_name,
        embedding_model=config['embedding_model'],
        api_token=config['api_token'],
        debug_level="NONE"
    )

    print("Archive upload completed successfully")


def upload_s3(bucket_name: str, collection_name: str, prefix: str = "",
              s3_endpoint: str = None):
    """Execute S3 bucket upload."""
    from app.handlers import S3Handler

    config = _get_env_config()
    if not config['embedding_model'] or not config['api_token']:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")

    print(f"Uploading S3 bucket: {bucket_name}/{prefix}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {config['embedding_model']}")
    print(f"Region: {region}")

    handler = S3Handler()
    handler.handle(
        bucket_name=bucket_name,
        collection_name=collection_name,
        embedding_model=config['embedding_model'],
        api_token=config['api_token'],
        prefix=prefix,
        s3_endpoint=s3_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_region=region,
        debug_level="NONE",
        qdrant_host=config['qdrant_host'],
        qdrant_port=config['qdrant_port']
    )

    print("S3 bucket upload completed successfully")


def collection_create(collection_name: str, dimension: str):
    """Create a collection."""
    from app.qdrant_manager import QdrantManager

    config = _get_env_config()
    if not config['embedding_model']:
        raise ValueError("MODEL_NAME environment variable required")

    print(f"Creating collection: {collection_name}")
    print(f"Dimension: {dimension}")
    print(f"Embedding Model: {config['embedding_model']}")

    manager = QdrantManager(host=config['qdrant_host'], port=config['qdrant_port'])
    manager.create_collection(collection_name, int(dimension), config['embedding_model'])

    print(f"Collection '{collection_name}' created successfully")


def collection_delete(collection_name: str):
    """Delete a collection."""
    from app.qdrant_manager import QdrantManager

    config = _get_env_config()

    print(f"Deleting collection: {collection_name}")

    manager = QdrantManager(host=config['qdrant_host'], port=config['qdrant_port'])
    manager.delete_collection(collection_name)

    print(f"Collection '{collection_name}' deleted successfully")


def collection_list():
    """List all collections."""
    from app.qdrant_manager import QdrantManager

    config = _get_env_config()

    print("Listing collections from Qdrant")

    manager = QdrantManager(host=config['qdrant_host'], port=config['qdrant_port'])
    collections = manager.list_collections()

    if collections:
        print("\nCollections:")
        for collection in collections:
            print(f"  - {collection}")
    else:
        print("No collections found")


def main():
    """Main entry point for worker."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.worker <operation> <args...>")
        print("\nOperations:")
        print("  upload_repo <repo_url> <collection> [--git-token <token>]")
        print("  upload_file <file_path> <collection>")
        print("  upload_archive <archive_path> <collection>")
        print("  upload_s3 <bucket> <collection> [--prefix <prefix>] [--endpoint <url>]")
        print("  collection_create <name> <dimension>")
        print("  collection_delete <name>")
        print("  collection_list")
        sys.exit(1)

    operation = sys.argv[1]
    args = sys.argv[2:]

    try:
        if operation == "upload_repo":
            if len(args) < 2:
                raise ValueError("upload_repo requires: <repo_url> <collection>")
            git_token = None
            if "--git-token" in args:
                token_idx = args.index("--git-token")
                git_token = args[token_idx + 1]
                args = [a for i, a in enumerate(args) if i not in [token_idx, token_idx + 1]]
            upload_repo(args[0], args[1], git_token)

        elif operation == "upload_file":
            if len(args) < 2:
                raise ValueError("upload_file requires: <file_path> <collection>")
            upload_file(args[0], args[1])

        elif operation == "upload_archive":
            if len(args) < 2:
                raise ValueError("upload_archive requires: <archive_path> <collection>")
            upload_archive(args[0], args[1])

        elif operation == "upload_s3":
            if len(args) < 2:
                raise ValueError("upload_s3 requires: <bucket> <collection> [--prefix <prefix>] [--endpoint <url>]")

            # Parse optional arguments
            prefix = ""
            endpoint = None

            if "--prefix" in args:
                idx = args.index("--prefix")
                prefix = args[idx + 1]
                args = [a for i, a in enumerate(args) if i not in [idx, idx + 1]]

            if "--endpoint" in args:
                idx = args.index("--endpoint")
                endpoint = args[idx + 1]
                args = [a for i, a in enumerate(args) if i not in [idx, idx + 1]]

            upload_s3(args[0], args[1], prefix, endpoint)

        elif operation == "collection_create":
            if len(args) < 2:
                raise ValueError("collection_create requires: <name> <dimension>")
            collection_create(args[0], args[1])

        elif operation == "collection_delete":
            if len(args) < 1:
                raise ValueError("collection_delete requires: <name>")
            collection_delete(args[0])

        elif operation == "collection_list":
            collection_list()

        else:
            print(f"Unknown operation: {operation}")
            sys.exit(1)

    except Exception as e:
        print(f"Error executing {operation}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
