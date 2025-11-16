"""
Worker entry point for job execution.

This module is the entry point when running jobs in containers.
It handles the actual execution of operations (upload, collection management, etc.).

Usage:
    python -m app.worker <operation> <args...>

Examples:
    python -m app.worker upload_repo https://github.com/user/repo.git collection_name
    python -m app.worker upload_file /data/file.pdf collection_name
    python -m app.worker upload_archive /data/docs.zip collection_name
    python -m app.worker collection_create my_collection 1536
    python -m app.worker collection_delete my_collection
    python -m app.worker collection_list
"""

import sys
import os
from pathlib import Path

# Ensure app module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


def upload_repo(repo_url: str, collection_name: str, git_token: str = None):
    """Execute repository upload."""
    from app.handlers import RepoHandler

    # Get config from environment
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    embedding_model = os.getenv("MODEL_NAME")
    api_token = os.getenv("API_TOKEN")
    github_token = git_token or os.getenv("GITHUB_TOKEN")

    if not embedding_model or not api_token:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    print(f"Uploading repository: {repo_url}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {embedding_model}")
    print(f"Qdrant: {qdrant_host}:{qdrant_port}")

    handler = RepoHandler()
    handler.handle(
        git_url=repo_url,
        collection_name=collection_name,
        embedding_model=embedding_model,
        api_token=api_token,
        git_token=github_token,
        debug_level="NONE"
    )

    print("Repository upload completed successfully")


def upload_file(file_path: str, collection_name: str):
    """Execute file upload."""
    from app.handlers import FileHandler

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    embedding_model = os.getenv("MODEL_NAME")
    api_token = os.getenv("API_TOKEN")

    if not embedding_model or not api_token:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    print(f"Uploading file: {file_path}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {embedding_model}")

    FileHandler.handle(
        file_path=file_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        api_token=api_token,
        debug_level="NONE"
    )

    print("File upload completed successfully")


def upload_archive(archive_path: str, collection_name: str):
    """Execute archive upload."""
    from app.handlers import ArchiveHandler

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    embedding_model = os.getenv("MODEL_NAME")
    api_token = os.getenv("API_TOKEN")

    if not embedding_model or not api_token:
        raise ValueError("MODEL_NAME and API_TOKEN environment variables required")

    print(f"Uploading archive: {archive_path}")
    print(f"Collection: {collection_name}")
    print(f"Embedding Model: {embedding_model}")

    handler = ArchiveHandler()
    handler.handle(
        archive_path=archive_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        api_token=api_token,
        debug_level="NONE"
    )

    print("Archive upload completed successfully")


def collection_create(collection_name: str, dimension: str):
    """Create a collection."""
    from app.qdrant_manager import QdrantManager

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

    print(f"Creating collection: {collection_name}")
    print(f"Dimension: {dimension}")
    print(f"Qdrant: {qdrant_host}:{qdrant_port}")

    manager = QdrantManager(host=qdrant_host, port=qdrant_port)
    manager.create_collection(collection_name, int(dimension))

    print(f"Collection '{collection_name}' created successfully")


def collection_delete(collection_name: str):
    """Delete a collection."""
    from app.qdrant_manager import QdrantManager

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

    print(f"Deleting collection: {collection_name}")
    print(f"Qdrant: {qdrant_host}:{qdrant_port}")

    manager = QdrantManager(host=qdrant_host, port=qdrant_port)
    manager.delete_collection(collection_name)

    print(f"Collection '{collection_name}' deleted successfully")


def collection_list():
    """List all collections."""
    from app.qdrant_manager import QdrantManager

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

    print(f"Listing collections from Qdrant: {qdrant_host}:{qdrant_port}")

    manager = QdrantManager(host=qdrant_host, port=qdrant_port)
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
