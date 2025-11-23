"""
QdrantManager: Centralized interface for all Qdrant operations.

This module provides a unified interface for:
- Collection management (create, delete, list, info)
- Chunk upload operations
- Collection existence checks
- Syncing operations (repos, archives, files)

All Qdrant-related logic should go through this manager.
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import tempfile
import subprocess
import hashlib
import os
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, CollectionInfo, Filter, FieldCondition, MatchText
from app.embedder import Embedder
from app.qdrant_chunker import file_to_qdrant_chunks
from app.git_utils import smart_git_clone, get_repo_name_from_url, GitCloneError
from app.logger import get_logger

logger = get_logger(__name__)


class QdrantManager:
    """
    Centralized manager for all Qdrant vector database operations.

    Handles collection lifecycle and data upload operations.
    """

    def __init__(self, host: str = "localhost", port: int = 6333):
        """
        Initialize QdrantManager with connection parameters.

        Args:
            host: Qdrant server host (default: localhost)
            port: Qdrant server port (default: 6333)
        """
        self.client = QdrantClient(host=host, port=port)
        # Cache embedder instances to avoid recreating them
        self._embedder_cache = {}

    def _get_embedder(self, embedding_model: str, api_token: str) -> Embedder:
        """
        Get or create a cached Embedder instance.

        Args:
            embedding_model: Embedding model name
            api_token: API token for embedding service

        Returns:
            Cached or new Embedder instance
        """
        cache_key = f"{embedding_model}:{api_token[:10]}"  # Use first 10 chars of token for cache key

        if cache_key not in self._embedder_cache:
            self._embedder_cache[cache_key] = Embedder(model_name=embedding_model, api_token=api_token)

        return self._embedder_cache[cache_key]

    # ===== COLLECTION MANAGEMENT =====

    def create_collection(self, collection_name: str, vector_size: int,
                         embedding_model: str, distance: Distance = Distance.COSINE):
        """
        Create a new Qdrant collection with specified vector configuration.

        Args:
            collection_name: Name of the collection to create
            vector_size: Dimension of vectors (e.g., 3072 for text-embedding-3-large)
            embedding_model: Embedding model used for this collection (e.g., "Qwen/Qwen3-Embedding-8B") - REQUIRED
            distance: Distance metric (default: COSINE)

        Raises:
            Exception: If collection already exists or creation fails
        """
        if self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' already exists")

        # Create collection
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance)
        )

        # Store embedding model as a special metadata point
        # Use a reserved UUID that won't conflict with document chunks
        import uuid
        metadata_point_id = str(uuid.UUID('00000000-0000-0000-0000-000000000000'))

        self.client.upsert(
            collection_name=collection_name,
            points=[{
                "id": metadata_point_id,
                "vector": [0.0] * vector_size,  # Zero vector
                "payload": {
                    "_collection_metadata": True,
                    "embedding_model": embedding_model,
                    "vector_size": vector_size,
                    "distance": distance.value if hasattr(distance, 'value') else str(distance)
                }
            }]
        )

        logger.info(f"Created collection '{collection_name}' with vector size {vector_size}, embedding model: {embedding_model}")

    def delete_collection(self, collection_name: str):
        """
        Delete a Qdrant collection and all its data.

        Args:
            collection_name: Name of the collection to delete

        Raises:
            Exception: If collection doesn't exist or deletion fails
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        self.client.delete_collection(collection_name=collection_name)
        logger.info(f"Deleted collection '{collection_name}'")

    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection_name: Name of the collection to check

        Returns:
            True if collection exists, False otherwise
        """
        return self.client.collection_exists(collection_name)

    def list_collections(self) -> List[str]:
        """
        List all collections in the Qdrant instance.

        Returns:
            List of collection names
        """
        collections = self.client.get_collections()
        return [col.name for col in collections.collections]

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary containing collection metadata

        Raises:
            Exception: If collection doesn't exist
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        info: CollectionInfo = self.client.get_collection(collection_name)

        result = {
            "name": collection_name,
            "vector_size": info.config.params.vectors.size,
            "distance": info.config.params.vectors.distance,
            "points_count": info.points_count,
            "status": info.status
        }

        # Try to get embedding model from metadata point
        try:
            embedding_model = self.get_collection_embedding_model(collection_name)
            result['embedding_model'] = embedding_model
        except ValueError:
            # No embedding model metadata found
            pass

        return result

    def get_collection_embedding_model(self, collection_name: str) -> str:
        """
        Get the embedding model for a collection from its metadata point.

        Args:
            collection_name: Name of the collection

        Returns:
            Embedding model name stored in collection metadata

        Raises:
            ValueError: If collection doesn't exist or embedding_model not found
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        # Try to retrieve the special metadata point
        import uuid
        metadata_point_id = str(uuid.UUID('00000000-0000-0000-0000-000000000000'))

        try:
            points = self.client.retrieve(
                collection_name=collection_name,
                ids=[metadata_point_id]
            )

            if points and len(points) > 0:
                payload = points[0].payload
                if payload and '_collection_metadata' in payload and payload.get('embedding_model'):
                    return payload['embedding_model']

        except Exception:
            # Metadata point doesn't exist or retrieval failed
            pass

        raise ValueError(
            f"Collection '{collection_name}' does not have embedding_model metadata. "
            f"This collection was created without specifying an embedding model."
        )

    # ===== DATA UPLOAD =====

    def upload_chunks(self, collection_name: str, qdrant_chunks: List, embedder: Embedder):
        """
        Upload document chunks to an existing collection with concurrent embedding generation.

        IMPORTANT: This method assumes the collection already exists.
        It will NOT create the collection automatically.

        Args:
            collection_name: Name of the target collection (must exist)
            qdrant_chunks: List of QdrantChunk objects
            embedder: Embedder instance for generating vectors

        Raises:
            ValueError: If collection doesn't exist
            Exception: If upload fails
        """
        if not self.collection_exists(collection_name):
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Please create it first using create_collection()."
            )

        # Generate embeddings concurrently with ThreadPoolExecutor
        # Use 10 workers for good parallelism without overwhelming the API
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all embedding tasks
            future_to_chunk = {
                executor.submit(embedder.get_embedding, chunk.get_content()): chunk
                for chunk in qdrant_chunks
            }

            # Collect results as they complete
            points = []
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    vector = future.result()
                    points.append(PointStruct(
                        id=chunk.get_id(),
                        vector=vector,
                        payload={
                            "chunk_hash": chunk.get_chunk_hash(),
                            "parent_file_hash": chunk.get_file_hash(),
                            "file_path": chunk.get_relative_path(),
                            "text": chunk.get_content()
                        }
                    ))
                except Exception as e:
                    logger.error(f"Error generating embedding for chunk {chunk.get_id()}: {e}")
                    raise

        # Upload to Qdrant
        self.client.upsert(collection_name=collection_name, points=points)
        logger.info(f"Uploaded {len(points)} chunks to collection '{collection_name}'")

    def upload_chunks_with_embeddings(self, collection_name: str, qdrant_chunks: List,
                                     embedding_model: str, api_token: str, replace_existing: bool = True):
        """
        Upload document chunks to an existing collection (convenience method).

        This method uses a cached embedder instance for efficiency.
        By default, it intelligently replaces files only if content changed (hash differs).

        Args:
            collection_name: Name of the target collection (must exist)
            qdrant_chunks: List of QdrantChunk objects
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding service
            replace_existing: If True, check and replace files whose hash differs (default: True)

        Returns:
            Dict with stats: {'added': [(file, chunks)], 'modified': [(file, chunks)], 'unchanged': [(file, chunks)]}

        Raises:
            ValueError: If collection doesn't exist
            Exception: If upload fails
        """
        stats = {'added': [], 'modified': [], 'unchanged': []}

        if not replace_existing or not qdrant_chunks:
            embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)
            self.upload_chunks(collection_name, qdrant_chunks, embedder)
            # Can't determine stats without checking, assume all new
            for chunk in qdrant_chunks:
                stats['added'].append((chunk.get_relative_path(), 1))
            return stats

        # Group chunks by file_path and get their file hash
        file_groups = {}
        for chunk in qdrant_chunks:
            file_path = chunk.get_relative_path()
            file_hash = chunk.get_file_hash()

            if file_path not in file_groups:
                file_groups[file_path] = {
                    'chunks': [],
                    'new_hash': file_hash
                }
            file_groups[file_path]['chunks'].append(chunk)

        # Check each file against existing data
        chunks_to_upload = []

        for file_path, file_data in file_groups.items():
            new_hash = file_data['new_hash']
            file_chunks = file_data['chunks']
            num_chunks = len(file_chunks)

            # Get existing file info from Qdrant
            existing_hash = self._get_file_hash_from_collection(collection_name, file_path)

            if existing_hash is None:
                # New file - upload it
                logger.info(f"New file detected: {file_path}")
                chunks_to_upload.extend(file_chunks)
                stats['added'].append((file_path, num_chunks))
            elif existing_hash != new_hash:
                # File changed - replace it
                logger.info(f"File changed detected: {file_path}")
                self._delete_file_by_path(collection_name, file_path)
                chunks_to_upload.extend(file_chunks)
                stats['modified'].append((file_path, num_chunks))
            else:
                # File unchanged - skip it
                logger.info(f"File unchanged, skipping: {file_path}")
                stats['unchanged'].append((file_path, num_chunks))

        # Upload only the chunks that need to be uploaded
        if chunks_to_upload:
            embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)
            self.upload_chunks(collection_name, chunks_to_upload, embedder)
        else:
            logger.info("No files to upload (all files unchanged)")

        return stats

    # ===== SYNC HELPERS =====

    def _get_files_by_prefix(self, collection_name: str, prefix: str) -> Dict[str, Tuple[str, List[str]]]:
        """
        Get all points where file_path starts with prefix.

        Note: Qdrant doesn't support native prefix filtering, so we still need
        client-side filtering. However, we optimize by:
        - Using larger batch sizes to reduce API calls
        - Not fetching vectors (with_vectors=False)
        - Processing results in parallel

        Args:
            collection_name: Name of the collection
            prefix: File path prefix to filter by

        Returns:
            Dict mapping file_path -> (file_hash, [point_ids])
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        files = {}
        offset = None

        # Use larger batch size (1000 instead of 100) to reduce API calls
        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                limit=1000,  # Increased from 100 for better performance
                offset=offset,
                with_vectors=False,  # Don't need vectors, just metadata
                with_payload=True
            )

            # Process batch
            for point in results:
                file_path = point.payload.get('file_path', '')
                if file_path.startswith(prefix):
                    file_hash = point.payload.get('parent_file_hash', '')
                    if file_path not in files:
                        files[file_path] = (file_hash, [])
                    files[file_path][1].append(point.id)

            if offset is None:
                break

        return files

    def _delete_points(self, collection_name: str, point_ids: List[str]):
        """
        Delete specific points from a collection.

        Args:
            collection_name: Name of the collection
            point_ids: List of point IDs to delete
        """
        if not point_ids:
            return

        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        self.client.delete(
            collection_name=collection_name,
            points_selector=point_ids
        )
        logger.info(f"Deleted {len(point_ids)} points from collection '{collection_name}'")

    def _delete_file_by_path(self, collection_name: str, file_path: str) -> int:
        """
        Delete all chunks of a specific file from the collection.

        Args:
            collection_name: Name of the collection
            file_path: The file_path value to match and delete

        Returns:
            Number of chunks deleted
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        # Find all points with this file_path
        point_ids = []
        offset = None

        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                with_vectors=False,
                with_payload=True
            )

            for point in results:
                if point.payload.get('file_path') == file_path:
                    point_ids.append(point.id)

            if offset is None:
                break

        # Delete found points
        if point_ids:
            self.client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            logger.info(f"Deleted {len(point_ids)} existing chunks for file '{file_path}'")

        return len(point_ids)

    def _get_file_hash_from_collection(self, collection_name: str, file_path: str) -> str:
        """
        Get the file hash for a specific file from the collection.

        Args:
            collection_name: Name of the collection
            file_path: The file_path value to look up

        Returns:
            File hash if found, None otherwise
        """
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        # Find first point with this file_path and return its hash
        offset = None

        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                with_vectors=False,
                with_payload=True
            )

            for point in results:
                if point.payload.get('file_path') == file_path:
                    # Found it - return the hash
                    return point.payload.get('parent_file_hash')

            if offset is None:
                break

        # Not found
        return None

    def _hash_file(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of a file using streaming for memory efficiency.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of file hash
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read in 64KB chunks to avoid loading entire file into memory
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _scan_files(self, directory: Path, prefix: str = "") -> Dict[str, str]:
        """
        Scan directory and build file state map.

        Args:
            directory: Directory to scan
            prefix: Prefix to prepend to relative paths (e.g., "repo-name/")

        Returns:
            Dict mapping file_path -> file_hash
        """
        file_state = {}

        for file_path in directory.rglob("*"):
            if file_path.is_file() and not self._should_skip_file(file_path):
                rel_path = file_path.relative_to(directory)
                full_path = f"{prefix}{rel_path}" if prefix else str(rel_path)
                file_hash = self._hash_file(file_path)
                file_state[full_path] = (file_hash, file_path)

        return file_state

    def _should_skip_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be skipped during processing.

        Args:
            file_path: Path to check

        Returns:
            True if file should be skipped
        """
        # Skip hidden files and common non-text directories
        skip_patterns = {'.git', '__pycache__', 'node_modules', '.env', '.venv'}

        for part in file_path.parts:
            if part in skip_patterns or part.startswith('.'):
                return True

        return False

    # ===== SYNC OPERATIONS =====

    def sync_repo(self, git_url: str, collection_name: str, embedding_model: str, api_token: str,
                  debug_level: str = "NONE", git_token: str = None) -> Dict[str, int]:
        """
        Sync a git repository to Qdrant collection.

        Clones repo, compares with existing state, and syncs changes:
        - Deletes chunks for removed files
        - Adds chunks for new files
        - Re-chunks and re-embeds modified files

        Smart authentication:
        - Tries to clone without auth first (public repos)
        - For SSH: Auto-detects keys from ~/.ssh/ (id_rsa, id_ed25519, etc.)
        - For HTTPS: Uses git_token if provided
        - Container-friendly: finds mounted SSH keys automatically

        Args:
            git_url: Git repository URL (HTTPS or SSH format)
            collection_name: Target collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
            git_token: Personal access token for private HTTPS repos (optional)

        Returns:
            Dict with sync statistics: {'added': N, 'updated': N, 'deleted': N}
        """
        # Extract repo name from URL
        repo_name = get_repo_name_from_url(git_url)

        logger.info(f"Syncing repository '{repo_name}' from {git_url}")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"

            # Smart clone with auto-detection and fallback
            logger.info("Cloning repository")
            try:
                smart_git_clone(
                    git_url=git_url,
                    destination=repo_path,
                    git_token=git_token
                )
                logger.info("✓ Repository cloned successfully")
            except GitCloneError as e:
                logger.error(f"Git Clone Failed: {e}")
                raise

            # Sync with prefix
            return self._sync_files(
                collection_name=collection_name,
                prefix=f"{repo_name}/",
                source_directory=repo_path,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level
            )

    def sync_file(self, file_path: str, collection_name: str, embedding_model: str, api_token: str, debug_level: str = "NONE") -> Dict[str, int]:
        """
        Sync a single file to Qdrant collection.

        Args:
            file_path: Path to the file
            collection_name: Target collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")

        Returns:
            Dict with sync statistics: {'added': N, 'updated': N, 'deleted': N}
        """
        file_path = Path(file_path).absolute()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Syncing file '{file_path.name}'")

        # Create temp directory with just this file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Use just the filename as the identifier
            return self._sync_files(
                collection_name=collection_name,
                prefix="",
                source_directory=file_path.parent,
                embedding_model=embedding_model,
                api_token=api_token,
                specific_files=[file_path.name],
                debug_level=debug_level
            )

    def _sync_files(self, collection_name: str, prefix: str, source_directory: Path,
                   embedding_model: str, api_token: str, specific_files: List[str] = None, debug_level: str = "NONE") -> Dict[str, int]:
        """
        Core sync logic - compares current state with Qdrant and syncs.

        Args:
            collection_name: Target collection
            prefix: Prefix for file paths (e.g., "repo-name/")
            source_directory: Directory containing source files
            embedding_model: Embedding model (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token
            specific_files: If provided, only sync these files (for single file sync)
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")

        Returns:
            Sync statistics
        """
        embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)

        # Build current file state
        logger.info("Scanning source directory")
        if specific_files:
            # Single file mode
            current_files = {}
            for filename in specific_files:
                file_path = source_directory / filename
                if file_path.exists():
                    file_hash = self._hash_file(file_path)
                    current_files[filename] = (file_hash, file_path)
        else:
            # Full directory scan
            current_files = self._scan_files(source_directory, prefix)

        logger.info(f"Found {len(current_files)} file(s) in source")

        # Get existing state from Qdrant
        logger.info(f"Querying Qdrant for existing files with prefix '{prefix}'")
        qdrant_files = self._get_files_by_prefix(collection_name, prefix)
        logger.info(f"Found {len(qdrant_files)} file(s) in Qdrant")

        # Determine operations
        to_delete = []
        to_update = []
        to_add = []

        # Check for deletions and updates
        for file_path, (old_hash, point_ids) in qdrant_files.items():
            if file_path not in current_files:
                # File was deleted
                to_delete.extend(point_ids)
                logger.info(f"DELETE: {file_path}")
            elif current_files[file_path][0] != old_hash:
                # File was modified (hash changed)
                to_update.append((file_path, point_ids, current_files[file_path][1]))
                logger.info(f"UPDATE: {file_path}")

        # Check for additions
        for file_path in current_files:
            if file_path not in qdrant_files:
                to_add.append((file_path, current_files[file_path][1]))
                logger.info(f"ADD: {file_path}")

        # Execute operations
        stats = {'added': 0, 'updated': 0, 'deleted': 0}

        # Delete removed files
        if to_delete:
            logger.info(f"Deleting {len(to_delete)} chunks from removed files")
            self._delete_points(collection_name, to_delete)
            stats['deleted'] = len(to_delete)

        # Update modified files (delete old + add new)
        if to_update:
            logger.info(f"Updating {len(to_update)} modified file(s)")

            # Parallelize file chunking for updates
            def process_update(file_data):
                file_path, old_point_ids, physical_path = file_data
                logger.info(f"Re-chunking {file_path}")
                chunks = file_to_qdrant_chunks(str(physical_path), embedding_model, file_path, debug_level)
                return file_path, old_point_ids, chunks

            with ThreadPoolExecutor(max_workers=4) as executor:
                update_results = list(executor.map(process_update, to_update))

            # Delete old and upload new sequentially (to avoid race conditions)
            for file_path, old_point_ids, chunks in update_results:
                self._delete_points(collection_name, old_point_ids)
                self.upload_chunks(collection_name, chunks, embedder)
                stats['updated'] += 1

        # Add new files
        if to_add:
            logger.info(f"Adding {len(to_add)} new file(s)")

            # Parallelize file chunking for additions
            def process_addition(file_data):
                file_path, physical_path = file_data
                logger.info(f"Chunking {file_path}")
                chunks = file_to_qdrant_chunks(str(physical_path), embedding_model, file_path, debug_level)
                return chunks

            with ThreadPoolExecutor(max_workers=4) as executor:
                all_chunks = list(executor.map(process_addition, to_add))

            # Upload all chunks
            for chunks in all_chunks:
                self.upload_chunks(collection_name, chunks, embedder)
                stats['added'] += 1

        logger.info(f"Sync complete: {stats['added']} added, {stats['updated']} updated, {stats['deleted']} chunks deleted")
        return stats

    def sync_archive(self, archive_path: str, collection_name: str, embedding_model: str, api_token: str, debug_level: str = "NONE") -> Dict[str, int]:
        """
        Sync an archive file to Qdrant collection.

        Intelligently handles archive contents:
        - Detects git repos (directories with .git) and preserves structure
        - Flattens loose files (just filename, no path)

        Args:
            archive_path: Path to archive file (.zip, .tar, .tar.gz, etc.)
            collection_name: Target collection name
            embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")

        Returns:
            Dict with sync statistics: {'added': N, 'updated': N, 'deleted': N}
        """
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        logger.info(f"Syncing archive: {archive_path.name}")

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            # Extract archive
            logger.info("Extracting archive")
            self._extract_archive(archive_path, extract_path)

            # Analyze contents
            logger.info("Analyzing contents")
            analysis = self._analyze_archive_contents(extract_path)

            logger.info(f"Found {len(analysis['repos'])} git repository(ies) and {len(analysis['files'])} loose file(s)")

            total_stats = {'added': 0, 'updated': 0, 'deleted': 0}

            # Sync each repo found
            for repo_info in analysis['repos']:
                repo_name = repo_info['name']
                repo_path = repo_info['path']
                logger.info(f"Syncing repo: {repo_name}")

                stats = self._sync_files(
                    collection_name=collection_name,
                    prefix=f"{repo_name}/",
                    source_directory=repo_path,
                    embedding_model=embedding_model,
                    api_token=api_token,
                    debug_level=debug_level
                )

                total_stats['added'] += stats['added']
                total_stats['updated'] += stats['updated']
                total_stats['deleted'] += stats['deleted']

            # Sync loose files (flattened)
            if analysis['files']:
                logger.info(f"Syncing {len(analysis['files'])} loose file(s)")
                embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)

                for file_info in analysis['files']:
                    file_path = file_info['path']
                    filename = file_info['name']

                    # Check if file exists in Qdrant
                    qdrant_files = self._get_files_by_prefix(collection_name, filename)

                    if filename in qdrant_files:
                        # Check if hash changed
                        old_hash, old_point_ids = qdrant_files[filename]
                        new_hash = self._hash_file(file_path)

                        if old_hash != new_hash:
                            # Update file
                            logger.info(f"Updating {filename}")
                            self._delete_points(collection_name, old_point_ids)
                            chunks = file_to_qdrant_chunks(str(file_path), embedding_model, filename, debug_level)
                            self.upload_chunks(collection_name, chunks, embedder)
                            total_stats['updated'] += 1
                    else:
                        # New file
                        logger.info(f"Adding {filename}")
                        chunks = file_to_qdrant_chunks(str(file_path), embedding_model, filename, debug_level)
                        self.upload_chunks(collection_name, chunks, embedder)
                        total_stats['added'] += 1

            logger.info(f"Archive sync complete: {total_stats['added']} added, {total_stats['updated']} updated, {total_stats['deleted']} chunks deleted")
            return total_stats

    def _analyze_archive_contents(self, extract_path: Path) -> Dict[str, List]:
        """
        Analyze extracted archive to identify repos vs loose files.

        Walks the directory tree and identifies:
        - Git repositories (directories containing .git)
        - Loose files (everything else, flattened by name only)

        Args:
            extract_path: Path to extracted archive contents

        Returns:
            Dict with 'repos' and 'files' lists
        """
        repos = []
        files = []
        processed_paths = set()

        # First pass: Find all git repos
        for root, dirs, filenames in os.walk(extract_path):
            root_path = Path(root)

            # Skip if we're inside an already-found repo
            if any(root_path == p or root_path.is_relative_to(p) for p in processed_paths):
                continue

            # Check for .git directory or file (submodules)
            if '.git' in dirs or '.git' in filenames:
                # Found a repo!
                repo_name = root_path.name
                repos.append({
                    'name': repo_name,
                    'path': root_path
                })
                processed_paths.add(root_path)
                logger.info(f"Found repo: {repo_name}")

        # Second pass: Collect loose files (not in repos)
        for file_path in extract_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip if inside a repo
            if any(file_path.is_relative_to(repo_path) for repo_path in processed_paths):
                continue

            # Skip if should be ignored
            if self._should_skip_file(file_path):
                continue

            # Loose file - use flattened name only
            files.append({
                'name': file_path.name,
                'path': file_path
            })

        return {'repos': repos, 'files': files}

    def _extract_archive(self, archive_path: Path, extract_to: Path):
        """
        Extract archive file based on its extension.

        Args:
            archive_path: Path to archive
            extract_to: Directory to extract to
        """
        suffix = archive_path.suffix.lower()

        if suffix == ".zip":
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)

        elif suffix in [".tar", ".gz", ".bz2", ".xz"] or ".tar." in archive_path.name.lower():
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)

        else:
            raise ValueError(f"Unsupported archive format: {suffix}")
