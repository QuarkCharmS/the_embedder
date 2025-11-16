#!/usr/bin/env python3
"""
RAG in AWS - Command Line Interface

A CLI tool for ingesting documents, repositories, and archives into Qdrant vector database
with automatic chunking and embedding generation.
"""

import argparse
import os
import sys
from typing import Optional
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system environment variables

# Import handlers and managers
from app.handlers import FileHandler, RepoHandler, ArchiveHandler
from app.qdrant_manager import QdrantManager
from qdrant_client.models import Distance


class RAGCli:
    """Main CLI application class."""

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser with all commands and options."""
        parser = argparse.ArgumentParser(
            description="RAG in AWS - Ingest documents into Qdrant vector database",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Environment Variables:
  QDRANT_HOST              Qdrant server host (default: localhost)
  QDRANT_PORT              Qdrant server port (default: 6333)
  MODEL_NAME               Embedding model name
  API_TOKEN                API token for your embedding provider (recommended)
  GITHUB_TOKEN             GitHub personal access token (for private repos)
  DEBUG                    Enable verbose output (true/false)

Model Support:
  This CLI supports any embedding model compatible with your embedder.
  Common examples include:
    - Qwen/Qwen3-Embedding-8B (DeepInfra)
    - text-embedding-3-small, text-embedding-3-large (OpenAI)
    - voyage-2, voyage-code-2 (Voyage AI)
    - And many more...

  Specify your model with --model and provide the appropriate API token.

Examples:
  # Upload a repository (uses MODEL_NAME and API_TOKEN from .env)
  rag-cli upload repo https://github.com/user/repo.git my_collection

  # IMPORTANT: Global options (--model, --api-token, etc.) must come BEFORE the command
  # Upload with custom Qdrant host and explicit model
  rag-cli --qdrant-host qdrant.example.com \\
    --model Qwen/Qwen3-Embedding-8B \\
    --api-token $API_TOKEN \\
    upload repo https://github.com/user/repo.git my_collection

  # Upload a single file with verbose output
  rag-cli --debug upload file /path/to/document.pdf my_collection

  # Upload archive with environment variables
  export API_TOKEN=xxx
  export MODEL_NAME=text-embedding-3-large
  rag-cli upload archive project.tar.gz my_collection

  # List and manage collections
  rag-cli collections list
  rag-cli collections create my_collection --vector-size 4096 --embedding-model "Qwen/Qwen3-Embedding-8B"
  rag-cli collections info my_collection

Note:
  Upload is smart and incremental:
  - Only uploads new/changed files (hash comparison)
  - Skips unchanged files (no unnecessary API calls)
  - For repos: Automatically deletes chunks for removed files

Docker Usage:
  # Build the image
  docker build -t rag-cli .

  # Run with environment variables
  docker run -e API_TOKEN=xxx -e QDRANT_HOST=qdrant -e MODEL_NAME=your-model \\
    rag-cli upload repo https://github.com/user/repo.git my_collection

  # Run with env file
  docker run --env-file .env rag-cli --help
            """
        )

        # Global options
        parser.add_argument(
            '--qdrant-host',
            default=os.getenv('QDRANT_HOST', 'localhost'),
            help='Qdrant server host (env: QDRANT_HOST)'
        )
        parser.add_argument(
            '--qdrant-port',
            type=int,
            default=int(os.getenv('QDRANT_PORT', '6333')),
            help='Qdrant server port (env: QDRANT_PORT)'
        )
        parser.add_argument(
            '--model',
            default=os.getenv('MODEL_NAME'),
            help='Embedding model name (env: MODEL_NAME)'
        )
        parser.add_argument(
            '--api-token',
            default=self._get_api_token(),
            help='API token for your embedding provider (env: API_TOKEN)'
        )
        parser.add_argument(
            '--git-token',
            default=os.getenv('GITHUB_TOKEN'),
            help='GitHub personal access token for private repos (env: GITHUB_TOKEN)'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            default=os.getenv('DEBUG', '').lower() in ('true', '1', 'yes'),
            help='Enable verbose debug output (env: DEBUG)'
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s 1.0.0'
        )

        # Subcommands
        subparsers = parser.add_subparsers(dest='command', help='Command to execute')

        # Upload command
        upload_parser = subparsers.add_parser(
            'upload',
            help='Upload documents to Qdrant (smart sync: only uploads new/changed files, deletes removed files)'
        )
        self._add_upload_subcommands(upload_parser)

        # Collections command
        collections_parser = subparsers.add_parser(
            'collections',
            help='Manage Qdrant collections'
        )
        self._add_collections_subcommands(collections_parser)

        return parser

    def _add_upload_subcommands(self, parser: argparse.ArgumentParser):
        """Add subcommands for upload operations."""
        subparsers = parser.add_subparsers(dest='source_type', help='Source type to upload')

        # Upload file
        file_parser = subparsers.add_parser('file', help='Upload a single file')
        file_parser.add_argument('path', help='Path to the file')
        file_parser.add_argument('collection', help='Target collection name')

        # Upload repo
        repo_parser = subparsers.add_parser('repo', help='Upload a git repository')
        repo_parser.add_argument('url', help='Git repository URL (HTTPS or SSH)')
        repo_parser.add_argument('collection', help='Target collection name')

        # Upload archive
        archive_parser = subparsers.add_parser('archive', help='Upload an archive file')
        archive_parser.add_argument('path', help='Path to the archive (.zip, .tar.gz, etc.)')
        archive_parser.add_argument('collection', help='Target collection name')

    def _add_collections_subcommands(self, parser: argparse.ArgumentParser):
        """Add subcommands for collection management."""
        subparsers = parser.add_subparsers(dest='action', help='Collection action')

        # List collections
        subparsers.add_parser('list', help='List all collections')

        # Create collection
        create_parser = subparsers.add_parser('create', help='Create a new collection')
        create_parser.add_argument('name', help='Collection name')
        create_parser.add_argument(
            '--vector-size',
            type=int,
            required=True,
            help='Vector dimension size (required - must match your embedding model)'
        )
        create_parser.add_argument(
            '--distance',
            choices=['cosine', 'euclidean', 'dot'],
            default='cosine',
            help='Distance metric (default: cosine)'
        )
        create_parser.add_argument(
            '--embedding-model',
            type=str,
            required=True,
            help='Embedding model to use for this collection (e.g., "Qwen/Qwen3-Embedding-8B") - REQUIRED'
        )

        # Delete collection
        delete_parser = subparsers.add_parser('delete', help='Delete a collection')
        delete_parser.add_argument('name', help='Collection name')
        delete_parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

        # Info collection
        info_parser = subparsers.add_parser('info', help='Show collection information')
        info_parser.add_argument('name', help='Collection name')

    def _get_api_token(self) -> Optional[str]:
        """Get API token from environment variables.

        Checks API_TOKEN first (recommended), with fallback to legacy provider-specific
        variables for backward compatibility.
        """
        # Primary: Use the unified API_TOKEN
        token = os.getenv('API_TOKEN')
        if token:
            return token

        # Backward compatibility: Check legacy provider-specific variables
        # The embedder determines the correct provider based on model name,
        # so any of these tokens will work regardless of provider
        return (
            os.getenv('DEEPINFRA_TOKEN') or
            os.getenv('DEEPINFRA_API_TOKEN') or
            os.getenv('OPENAI_API_KEY') or
            os.getenv('COHERE_API_KEY') or
            os.getenv('VOYAGE_API_KEY')
        )

    def _get_debug_level(self, args) -> str:
        """Convert boolean debug flag to debug level string."""
        return "VERBOSE" if args.debug else "NONE"

    def _validate_args(self, args) -> bool:
        """Validate arguments and check for required values."""
        # Check if command was provided
        if not args.command:
            self.parser.print_help()
            return False

        # Validate API token for upload operations
        if args.command == 'upload':
            if not args.api_token:
                print("ERROR: API token is required for upload operations.", file=sys.stderr)
                print("\nSet the API_TOKEN environment variable for your embedding provider,", file=sys.stderr)
                print("or use the --api-token argument.", file=sys.stderr)
                print("\nExample: export API_TOKEN=your_api_key_here", file=sys.stderr)
                return False

            # Model is optional - will be fetched from collection metadata if not provided

            # Check if source type was provided
            if not args.source_type:
                print(f"ERROR: Please specify source type for {args.command} command.", file=sys.stderr)
                print(f"\nUsage: {sys.argv[0]} {args.command} [file|repo|archive] ...", file=sys.stderr)
                return False

        # Validate collections command
        if args.command == 'collections':
            if not args.action:
                print("ERROR: Please specify an action for collections command.", file=sys.stderr)
                print(f"\nUsage: {sys.argv[0]} collections [list|create|delete|info] ...", file=sys.stderr)
                return False

        return True

    def run(self, argv=None):
        """Main entry point for CLI execution."""
        args = self.parser.parse_args(argv)

        # Validate arguments
        if not self._validate_args(args):
            return 1

        try:
            # Route to appropriate handler
            if args.command == 'upload':
                return self._handle_upload(args)
            elif args.command == 'collections':
                return self._handle_collections(args)
            else:
                self.parser.print_help()
                return 1

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"\nERROR: {str(e)}", file=sys.stderr)
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1

    def _handle_upload(self, args) -> int:
        """Handle upload command."""
        debug_level = self._get_debug_level(args)

        print(f"Uploading {args.source_type} to collection '{args.collection}'...")
        print(f"Qdrant: {args.qdrant_host}:{args.qdrant_port}")

        try:
            # Check if collection exists BEFORE doing any expensive operations
            manager = QdrantManager(host=args.qdrant_host, port=args.qdrant_port)
            if not manager.collection_exists(args.collection):
                print(f"\nERROR: Collection '{args.collection}' does not exist.", file=sys.stderr)
                print(f"Create it first with:", file=sys.stderr)
                print(f"  python -m app.cli collections create {args.collection} --vector-size <size> --embedding-model <model>", file=sys.stderr)
                return 1

            # Get embedding model from collection metadata or use provided one
            try:
                collection_embedding_model = manager.get_collection_embedding_model(args.collection)

                if args.model:
                    # User provided a model - validate it matches collection's model
                    if args.model != collection_embedding_model:
                        print(f"\n⚠ WARNING: Provided model '{args.model}' differs from collection's model '{collection_embedding_model}'", file=sys.stderr)
                        print(f"Using collection's model: {collection_embedding_model}", file=sys.stderr)
                    embedding_model = collection_embedding_model
                else:
                    # No model provided - use collection's model
                    embedding_model = collection_embedding_model
                    print(f"Using embedding model from collection: {embedding_model}")

            except ValueError as e:
                # Collection doesn't have embedding_model in metadata
                if args.model:
                    # User provided model - use it
                    embedding_model = args.model
                    print(f"⚠ Collection has no embedding_model metadata. Using provided model: {embedding_model}")
                else:
                    # No model anywhere
                    print(f"\nERROR: Collection '{args.collection}' has no embedding_model metadata.", file=sys.stderr)
                    print(f"Please specify a model with --model flag.", file=sys.stderr)
                    return 1

            print(f"Embedding Model: {embedding_model}")
            if args.debug:
                print(f"Debug: Enabled")
            if args.source_type == 'file':
                file_path = Path(args.path).resolve()
                if not file_path.exists():
                    print(f"ERROR: File not found: {file_path}", file=sys.stderr)
                    return 1

                FileHandler.handle(
                    file_path=str(file_path),
                    collection_name=args.collection,
                    embedding_model=embedding_model,
                    api_token=args.api_token,
                    relative_path=file_path.name,
                    debug_level=debug_level
                )
                print(f"\n✓ Successfully uploaded file: {file_path.name}")

            elif args.source_type == 'repo':
                handler = RepoHandler()
                handler.handle(
                    git_url=args.url,
                    collection_name=args.collection,
                    embedding_model=embedding_model,
                    api_token=args.api_token,
                    debug_level=debug_level,
                    git_token=args.git_token
                )
                print(f"\n✓ Successfully uploaded repository: {args.url}")

            elif args.source_type == 'archive':
                archive_path = Path(args.path).resolve()
                if not archive_path.exists():
                    print(f"ERROR: Archive not found: {archive_path}", file=sys.stderr)
                    return 1

                handler = ArchiveHandler()
                handler.handle(
                    archive_path=str(archive_path),
                    collection_name=args.collection,
                    embedding_model=embedding_model,
                    api_token=args.api_token,
                    debug_level=debug_level
                )
                print(f"\n✓ Successfully uploaded archive: {archive_path.name}")

            return 0

        except Exception as e:
            print(f"\nERROR during upload: {str(e)}", file=sys.stderr)
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1

    def _handle_collections(self, args) -> int:
        """Handle collections command."""
        manager = QdrantManager(host=args.qdrant_host, port=args.qdrant_port)

        try:
            if args.action == 'list':
                collections = manager.list_collections()
                if not collections:
                    print("No collections found.")
                    return 0

                print(f"Collections ({len(collections)}):")
                for name in sorted(collections):
                    print(f"  - {name}")
                return 0

            elif args.action == 'create':
                # Check if collection exists
                if manager.collection_exists(args.name):
                    print(f"ERROR: Collection '{args.name}' already exists.", file=sys.stderr)
                    return 1

                # Map distance string to Distance enum
                distance_map = {
                    'cosine': Distance.COSINE,
                    'euclidean': Distance.EUCLID,
                    'dot': Distance.DOT
                }
                distance = distance_map[args.distance]

                manager.create_collection(
                    collection_name=args.name,
                    vector_size=args.vector_size,
                    embedding_model=args.embedding_model,
                    distance=distance
                )
                print(f"✓ Created collection '{args.name}' (vector_size={args.vector_size}, distance={args.distance}, embedding_model={args.embedding_model})")
                return 0

            elif args.action == 'delete':
                # Check if collection exists
                if not manager.collection_exists(args.name):
                    print(f"ERROR: Collection '{args.name}' does not exist.", file=sys.stderr)
                    return 1

                # Confirm deletion unless --force
                if not args.force:
                    response = input(f"Are you sure you want to delete collection '{args.name}'? [y/N] ")
                    if response.lower() not in ('y', 'yes'):
                        print("Deletion cancelled.")
                        return 0

                manager.delete_collection(args.name)
                print(f"✓ Deleted collection '{args.name}'")
                return 0

            elif args.action == 'info':
                # Check if collection exists
                if not manager.collection_exists(args.name):
                    print(f"ERROR: Collection '{args.name}' does not exist.", file=sys.stderr)
                    return 1

                info = manager.get_collection_info(args.name)
                print(f"Collection: {args.name}")
                print(f"  Vector size: {info.get('vector_size', 'N/A')}")
                print(f"  Points count: {info.get('points_count', 'N/A')}")
                print(f"  Distance: {info.get('distance', 'N/A')}")
                if 'embedding_model' in info:
                    print(f"  Embedding model: {info['embedding_model']}")
                print(f"  Status: {info.get('status', 'N/A')}")
                return 0

            else:
                print(f"ERROR: Unknown action '{args.action}'", file=sys.stderr)
                return 1

        except Exception as e:
            print(f"\nERROR: {str(e)}", file=sys.stderr)
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1


def main():
    """Main entry point for the CLI application."""
    cli = RAGCli()
    sys.exit(cli.run())


if __name__ == '__main__':
    main()
