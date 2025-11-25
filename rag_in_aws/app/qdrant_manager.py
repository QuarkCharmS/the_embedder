"""
Centralized interface for Qdrant vector database operations.

Handles collection management, chunk uploads with embedding generation,
and intelligent syncing with hash-based change detection.

See ARCHITECTURE.md for detailed flow and logic.
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import tempfile
import hashlib
import os
import tarfile
import zipfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, CollectionInfo
from tqdm import tqdm
from app.embedder import Embedder
from app.qdrant_chunker import file_to_qdrant_chunks
from app.git_utils import smart_git_clone, get_repo_name_from_url, GitCloneError
from app.logger import get_logger

logger = get_logger(__name__)

_METADATA_POINT_ID = str(uuid.UUID('00000000-0000-0000-0000-000000000000'))
_SKIP_PATTERNS = {'.git', '__pycache__', 'node_modules', '.env', '.venv'}


class QdrantManager:
    """
    Centralized manager for all Qdrant vector database operations.

    Handles collection lifecycle and data upload operations.
    """

    def __init__(self, host: str = "localhost", port: int = 6333):
        """Initialize QdrantManager with connection parameters."""
        logger.info("QdrantManager connecting to %s:%s", host, port)
        # Increase timeout for large uploads (default is 5s, we use 300s = 5 minutes)
        self.client = QdrantClient(host=host, port=port, timeout=300)
        self._embedder_cache = {}
        logger.info("QdrantManager connected successfully")

    def _get_embedder(self, embedding_model: str, api_token: str) -> Embedder:
        """Get or create a cached Embedder instance."""
        cache_key = f"{embedding_model}:{api_token[:10]}"

        if cache_key not in self._embedder_cache:
            self._embedder_cache[cache_key] = Embedder(
                model_name=embedding_model, api_token=api_token
            )

        return self._embedder_cache[cache_key]

    # ===== COLLECTION MANAGEMENT =====

    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        embedding_model: str,
        distance: Distance = Distance.COSINE
    ):
        """Create a new Qdrant collection with specified vector configuration."""
        if self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' already exists")

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance)
        )

        # Store embedding model as metadata
        self.client.upsert(
            collection_name=collection_name,
            points=[{
                "id": _METADATA_POINT_ID,
                "vector": [0.0] * vector_size,
                "payload": {
                    "_collection_metadata": True,
                    "embedding_model": embedding_model,
                    "vector_size": vector_size,
                    "distance": distance.value if hasattr(distance, 'value') else str(distance)
                }
            }]
        )

        logger.info(
            "Created collection '%s' with vector size %s, embedding model: %s",
            collection_name, vector_size, embedding_model
        )

    def delete_collection(self, collection_name: str):
        """Delete a Qdrant collection and all its data."""
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        self.client.delete_collection(collection_name=collection_name)
        logger.info("Deleted collection '%s'", collection_name)

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        return self.client.collection_exists(collection_name)

    def list_collections(self) -> List[str]:
        """List all collections in the Qdrant instance."""
        collections = self.client.get_collections()
        return [col.name for col in collections.collections]

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get detailed information about a collection."""
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

        try:
            embedding_model = self.get_collection_embedding_model(collection_name)
            result['embedding_model'] = embedding_model
        except ValueError:
            pass

        return result

    def get_collection_embedding_model(self, collection_name: str) -> str:
        """Get the embedding model for a collection from its metadata point."""
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        try:
            points = self.client.retrieve(
                collection_name=collection_name,
                ids=[_METADATA_POINT_ID]
            )

            if points and len(points) > 0:
                payload = points[0].payload
                if payload and '_collection_metadata' in payload and payload.get('embedding_model'):
                    return payload['embedding_model']

        except Exception:
            pass

        raise ValueError(
            f"Collection '{collection_name}' does not have embedding_model metadata. "
            "This collection was created without specifying an embedding model."
        )

    # ===== DATA UPLOAD =====

    def upload_chunks(self, collection_name: str, qdrant_chunks: List, embedder: Embedder, debug_level: str = "NONE"):
        """
        Upload document chunks to collection with batch embedding and periodic uploads.

        Embeds in batches of 10 for API efficiency.
        Uploads every 100 points to balance memory usage and upload frequency.
        """
        if not self.collection_exists(collection_name):
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                "Please create it first using create_collection()."
            )

        embed_batch_size = 10  # Batch size for embedding API calls
        upload_batch_size = 100  # Upload every 100 points (reduced to avoid timeouts)
        points = []
        total_chunks = len(qdrant_chunks)
        uploaded_count = 0

        # Progress bar for chunk embedding and upload
        with tqdm(total=total_chunks, desc="Embedding & uploading", unit="chunk",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  disable=(debug_level != "VERBOSE")) as pbar:

            for i in range(0, total_chunks, embed_batch_size):
                batch_chunks = qdrant_chunks[i:i + embed_batch_size]
                batch_texts = [chunk.get_content() for chunk in batch_chunks]

                try:
                    # Step 1: Get embeddings for this batch (API call with 10 texts)
                    logger.debug("Embedding batch %s/%s (%s chunks)", i//embed_batch_size + 1, (total_chunks + embed_batch_size - 1)//embed_batch_size, len(batch_texts))
                    batch_embeddings = embedder.get_embeddings_batch(batch_texts)
                    logger.debug("Embeddings received, creating %s points", len(batch_embeddings))

                    # Step 2: Create points and accumulate
                    for chunk, embedding in zip(batch_chunks, batch_embeddings):
                        points.append(PointStruct(
                            id=chunk.get_id(),
                            vector=embedding,
                            payload={
                                "chunk_hash": chunk.get_chunk_hash(),
                                "parent_file_hash": chunk.get_file_hash(),
                                "file_path": chunk.get_relative_path(),
                                "text": chunk.get_content()
                            }
                        ))

                    # Step 3: Upload when we reach 1000 points
                    logger.debug("Accumulated %s points so far", len(points))
                    if len(points) >= upload_batch_size:
                        logger.info("Upserting %s points to Qdrant collection '%s'", len(points), collection_name)
                        self.client.upsert(collection_name=collection_name, points=points)
                        logger.info("✓ Upsert successful: %s points uploaded", len(points))
                        uploaded_count += len(points)
                        points = []  # Flush - clear the list

                    # Update progress bar
                    pbar.update(len(batch_chunks))

                except Exception as e:
                    logger.error("Error processing batch at index %s: %s", i, e)
                    raise

        # Upload any remaining points (the last batch, likely < 1000)
        if points:
            logger.info("Upserting final batch of %s points to Qdrant collection '%s'", len(points), collection_name)
            self.client.upsert(collection_name=collection_name, points=points)
            logger.info("✓ Final upsert successful: %s points uploaded", len(points))
            uploaded_count += len(points)

        logger.info("✓ Total uploaded: %s chunks to collection '%s'", uploaded_count, collection_name)

    def upload_chunks_with_embeddings(
        self,
        collection_name: str,
        qdrant_chunks: List,
        embedding_model: str,
        api_token: str,
        replace_existing: bool = True
    ):
        """Upload document chunks to an existing collection (convenience method)."""
        stats = {'added': [], 'modified': [], 'unchanged': []}

        if not replace_existing or not qdrant_chunks:
            embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)
            self.upload_chunks(collection_name, qdrant_chunks, embedder)
            for chunk in qdrant_chunks:
                stats['added'].append((chunk.get_relative_path(), 1))
            return stats

        # Group chunks by file_path
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

            existing_hash = self._get_file_hash_from_collection(collection_name, file_path)

            if existing_hash is None:
                logger.info("New file detected: %s", file_path)
                chunks_to_upload.extend(file_chunks)
                stats['added'].append((file_path, num_chunks))
            elif existing_hash != new_hash:
                logger.info("File changed detected: %s", file_path)
                self._delete_file_by_path(collection_name, file_path)
                chunks_to_upload.extend(file_chunks)
                stats['modified'].append((file_path, num_chunks))
            else:
                logger.info("File unchanged, skipping: %s", file_path)
                stats['unchanged'].append((file_path, num_chunks))

        if chunks_to_upload:
            embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)
            self.upload_chunks(collection_name, chunks_to_upload, embedder)
        else:
            logger.info("No files to upload (all files unchanged)")

        return stats

    # ===== SYNC HELPERS =====

    def get_all_file_hashes(self, collection_name: str, prefix: str = "",
                           include_point_ids: bool = False) -> Dict[str, any]:
        """
        Retrieve all file paths and their hashes from collection in bulk.

        Scrolls through the collection once and builds a complete dictionary.
        Much faster than checking files individually.

        Args:
            collection_name: Name of the collection
            prefix: Optional prefix to filter files (e.g., "repo_name/")
            include_point_ids: If True, returns {file_path: (hash, [point_ids])},
                             otherwise {file_path: hash}

        Returns:
            Dictionary mapping file_path -> parent_file_hash (or tuple with point_ids)
        """
        if not self.collection_exists(collection_name):
            return {}

        # Structure: {file_path: (hash, [point_ids])} if include_point_ids else {file_path: hash}
        file_data = {}
        offset = None
        batch_size = 10000

        logger.info("Fetching existing files from Qdrant (prefix: '%s')", prefix or "all")

        while True:
            results, next_offset = self.client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=["file_path", "parent_file_hash", "_collection_metadata"],
                with_vectors=False
            )

            if not results:
                break

            for point in results:
                # Skip metadata point
                if point.payload.get("_collection_metadata"):
                    continue

                file_path = point.payload.get("file_path")
                file_hash = point.payload.get("parent_file_hash")

                if not file_path or not file_hash:
                    continue

                # Filter by prefix if specified
                should_include = (not prefix) or file_path.startswith(prefix)

                if should_include:
                    if include_point_ids:
                        # Group by file_path and collect point IDs
                        if file_path not in file_data:
                            file_data[file_path] = (file_hash, [])
                        file_data[file_path][1].append(point.id)
                    else:
                        file_data[file_path] = file_hash

            if next_offset is None:
                break

            offset = next_offset

        logger.info("Found %s existing files in Qdrant", len(file_data))
        return file_data

    def get_point_ids_for_file(self, collection_name: str, file_path: str) -> List[str]:
        """
        Get all point IDs for a specific file.

        Args:
            collection_name: Name of the collection
            file_path: File path to get point IDs for

        Returns:
            List of point IDs (UUIDs as strings)
        """
        if not self.collection_exists(collection_name):
            return []

        point_ids = []
        offset = None

        # Scroll through collection looking for matching file_path
        while True:
            results, next_offset = self.client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                scroll_filter={
                    "must": [
                        {
                            "key": "file_path",
                            "match": {"value": file_path}
                        }
                    ]
                },
                with_payload=False,
                with_vectors=False
            )

            if not results:
                break

            for point in results:
                point_ids.append(point.id)

            if next_offset is None:
                break

            offset = next_offset

        return point_ids

    def check_file_status(self, collection_name: str, file_path: str, file_hash: str) -> str:
        """
        Check if a file needs to be uploaded based on hash comparison.

        Args:
            collection_name: Name of the collection
            file_path: Relative path of the file
            file_hash: SHA256 hash of the file content

        Returns:
            "new" - File doesn't exist in collection
            "modified" - File exists but hash changed
            "unchanged" - File exists with same hash
        """
        existing_hash = self._get_file_hash_from_collection(collection_name, file_path)

        if existing_hash is None:
            return "new"
        elif existing_hash != file_hash:
            return "modified"
        else:
            return "unchanged"

    def _get_files_by_prefix(
        self, collection_name: str, prefix: str
    ) -> Dict[str, Tuple[str, List[str]]]:
        """Get all points where file_path starts with prefix."""
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        files = {}
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
        """Delete specific points from a collection."""
        if not point_ids:
            return

        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        self.client.delete(
            collection_name=collection_name,
            points_selector=point_ids
        )
        logger.info("Deleted %s points from collection '%s'", len(point_ids), collection_name)

    def _delete_file_by_path(self, collection_name: str, file_path: str) -> int:
        """Delete all chunks of a specific file from the collection."""
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

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

        if point_ids:
            self.client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            logger.info("Deleted %s existing chunks for file '%s'", len(point_ids), file_path)

        return len(point_ids)

    def _get_file_hash_from_collection(self, collection_name: str, file_path: str) -> str:
        """Get the file hash for a specific file from the collection."""
        if not self.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

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
                    return point.payload.get('parent_file_hash')

            if offset is None:
                break

        return None

    def _hash_file(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file using streaming for memory efficiency."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _scan_files(self, directory: Path, prefix: str = "") -> Dict[str, Tuple[str, Path]]:
        """Scan directory and build file state map."""
        file_state = {}

        for file_path in directory.rglob("*"):
            if file_path.is_file() and not self._should_skip_file(file_path):
                rel_path = file_path.relative_to(directory)
                full_path = f"{prefix}{rel_path}" if prefix else str(rel_path)
                file_hash = self._hash_file(file_path)
                file_state[full_path] = (file_hash, file_path)

        return file_state

    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if a file should be skipped during processing."""
        for part in file_path.parts:
            if part in _SKIP_PATTERNS or part.startswith('.'):
                return True
        return False

    def _determine_sync_operations(self, current_files, qdrant_files):
        """Determine which files need to be added, updated, or deleted."""
        to_delete = []
        to_update = []
        to_add = []

        # Check for deletions and updates
        for file_path, (old_hash, point_ids) in qdrant_files.items():
            if file_path not in current_files:
                to_delete.extend(point_ids)
                logger.info("DELETE: %s", file_path)
            elif current_files[file_path][0] != old_hash:
                to_update.append((file_path, point_ids, current_files[file_path][1]))
                logger.info("UPDATE: %s", file_path)

        # Check for additions
        for file_path in current_files:
            if file_path not in qdrant_files:
                to_add.append((file_path, current_files[file_path][1]))
                logger.info("ADD: %s", file_path)

        return to_delete, to_update, to_add

    def _execute_deletions(self, collection_name, to_delete):
        """Execute deletion operations."""
        stats = {'deleted': 0}
        if to_delete:
            logger.info("Deleting %s chunks from removed files", len(to_delete))
            self._delete_points(collection_name, to_delete)
            stats['deleted'] = len(to_delete)
        return stats

    def _execute_updates(self, collection_name, to_update, embedding_model, debug_level, embedder):
        """Execute update operations."""
        stats = {'updated': 0}
        if not to_update:
            return stats

        logger.info("Updating %s modified file(s)", len(to_update))

        def process_update(file_data):
            file_path, old_point_ids, physical_path = file_data
            logger.info("Re-chunking %s", file_path)
            chunks = file_to_qdrant_chunks(
                str(physical_path), embedding_model, file_path, debug_level
            )
            return file_path, old_point_ids, chunks

        with ThreadPoolExecutor(max_workers=4) as executor:
            update_results = list(executor.map(process_update, to_update))

        for file_path, old_point_ids, chunks in update_results:
            self._delete_points(collection_name, old_point_ids)
            self.upload_chunks(collection_name, chunks, embedder)
            stats['updated'] += 1

        return stats

    def _execute_additions(self, collection_name, to_add, embedding_model, debug_level, embedder):
        """Execute addition operations."""
        stats = {'added': 0}
        if not to_add:
            return stats

        logger.info("Adding %s new file(s)", len(to_add))

        def process_addition(file_data):
            file_path, physical_path = file_data
            logger.info("Chunking %s", file_path)
            chunks = file_to_qdrant_chunks(
                str(physical_path), embedding_model, file_path, debug_level
            )
            return chunks

        with ThreadPoolExecutor(max_workers=4) as executor:
            all_chunks = list(executor.map(process_addition, to_add))

        for chunks in all_chunks:
            self.upload_chunks(collection_name, chunks, embedder)
            stats['added'] += 1

        return stats

    # ===== SYNC OPERATIONS =====

    def sync_repo(
        self,
        git_url: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        debug_level: str = "NONE",
        git_token: str = None
    ) -> Dict[str, int]:
        """Sync a git repository to Qdrant collection."""
        repo_name = get_repo_name_from_url(git_url)
        logger.info("Syncing repository '%s' from %s", repo_name, git_url)

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"

            logger.info("Cloning repository")
            try:
                smart_git_clone(
                    git_url=git_url,
                    destination=repo_path,
                    git_token=git_token
                )
                logger.info("✓ Repository cloned successfully")
            except GitCloneError as e:
                logger.error("Git Clone Failed: %s", e)
                raise

            return self._sync_files(
                collection_name=collection_name,
                prefix=f"{repo_name}/",
                source_directory=repo_path,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level
            )

    def sync_file(
        self,
        file_path: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        debug_level: str = "NONE"
    ) -> Dict[str, int]:
        """Sync a single file to Qdrant collection."""
        file_path = Path(file_path).absolute()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Syncing file '%s'", file_path.name)

        return self._sync_files(
            collection_name=collection_name,
            prefix="",
            source_directory=file_path.parent,
            embedding_model=embedding_model,
            api_token=api_token,
            specific_files=[file_path.name],
            debug_level=debug_level
        )

    def _sync_files(
        self,
        collection_name: str,
        prefix: str,
        source_directory: Path,
        embedding_model: str,
        api_token: str,
        specific_files: List[str] = None,
        debug_level: str = "NONE"
    ) -> Dict[str, int]:
        """Core sync logic - compares current state with Qdrant and syncs."""
        embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)

        # Build current file state
        logger.info("Scanning source directory")
        if specific_files:
            current_files = {}
            for filename in specific_files:
                file_path = source_directory / filename
                if file_path.exists():
                    file_hash = self._hash_file(file_path)
                    current_files[filename] = (file_hash, file_path)
        else:
            current_files = self._scan_files(source_directory, prefix)

        logger.info("Found %s file(s) in source", len(current_files))

        # Get existing state from Qdrant
        logger.info("Querying Qdrant for existing files with prefix '%s'", prefix)
        qdrant_files = self._get_files_by_prefix(collection_name, prefix)
        logger.info("Found %s file(s) in Qdrant", len(qdrant_files))

        # Determine operations
        to_delete, to_update, to_add = self._determine_sync_operations(
            current_files, qdrant_files
        )

        # Execute operations
        stats = {'added': 0, 'updated': 0, 'deleted': 0}

        delete_stats = self._execute_deletions(collection_name, to_delete)
        stats['deleted'] = delete_stats['deleted']

        update_stats = self._execute_updates(
            collection_name, to_update, embedding_model, debug_level, embedder
        )
        stats['updated'] = update_stats['updated']

        add_stats = self._execute_additions(
            collection_name, to_add, embedding_model, debug_level, embedder
        )
        stats['added'] = add_stats['added']

        logger.info(
            "Sync complete: %s added, %s updated, %s chunks deleted",
            stats['added'], stats['updated'], stats['deleted']
        )
        return stats

    def sync_archive(
        self,
        archive_path: str,
        collection_name: str,
        embedding_model: str,
        api_token: str,
        debug_level: str = "NONE"
    ) -> Dict[str, int]:
        """Sync an archive file to Qdrant collection."""
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        logger.info("Syncing archive: %s", archive_path.name)

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            logger.info("Extracting archive")
            self._extract_archive(archive_path, extract_path)

            logger.info("Analyzing contents")
            analysis = self._analyze_archive_contents(extract_path)

            logger.info(
                "Found %s git repository(ies) and %s loose file(s)",
                len(analysis['repos']), len(analysis['files'])
            )

            total_stats = {'added': 0, 'updated': 0, 'deleted': 0}

            # Sync each repo found
            for repo_info in analysis['repos']:
                repo_name = repo_info['name']
                repo_path = repo_info['path']
                logger.info("Syncing repo: %s", repo_name)

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

            # Sync loose files
            if analysis['files']:
                logger.info("Syncing %s loose file(s)", len(analysis['files']))
                embedder = self._get_embedder(embedding_model=embedding_model, api_token=api_token)

                for file_info in analysis['files']:
                    file_path = file_info['path']
                    filename = file_info['name']

                    qdrant_files = self._get_files_by_prefix(collection_name, filename)

                    if filename in qdrant_files:
                        old_hash, old_point_ids = qdrant_files[filename]
                        new_hash = self._hash_file(file_path)

                        if old_hash != new_hash:
                            logger.info("Updating %s", filename)
                            self._delete_points(collection_name, old_point_ids)
                            chunks = file_to_qdrant_chunks(
                                str(file_path), embedding_model, filename, debug_level
                            )
                            self.upload_chunks(collection_name, chunks, embedder)
                            total_stats['updated'] += 1
                    else:
                        logger.info("Adding %s", filename)
                        chunks = file_to_qdrant_chunks(
                            str(file_path), embedding_model, filename, debug_level
                        )
                        self.upload_chunks(collection_name, chunks, embedder)
                        total_stats['added'] += 1

            logger.info(
                "Archive sync complete: %s added, %s updated, %s chunks deleted",
                total_stats['added'], total_stats['updated'], total_stats['deleted']
            )
            return total_stats

    def _analyze_archive_contents(self, extract_path: Path) -> Dict[str, List]:
        """Analyze extracted archive to identify repos vs loose files."""
        repos = []
        files = []
        processed_paths = set()

        # First pass: Find all git repos
        for root, dirs, filenames in os.walk(extract_path):
            root_path = Path(root)

            if any(root_path == p or root_path.is_relative_to(p) for p in processed_paths):
                continue

            if '.git' in dirs or '.git' in filenames:
                repo_name = root_path.name
                repos.append({
                    'name': repo_name,
                    'path': root_path
                })
                processed_paths.add(root_path)
                logger.info("Found repo: %s", repo_name)

        # Second pass: Collect loose files
        for file_path in extract_path.rglob("*"):
            if not file_path.is_file():
                continue

            if any(file_path.is_relative_to(repo_path) for repo_path in processed_paths):
                continue

            if self._should_skip_file(file_path):
                continue

            files.append({
                'name': file_path.name,
                'path': file_path
            })

        return {'repos': repos, 'files': files}

    def _extract_archive(self, archive_path: Path, extract_to: Path):
        """Extract archive file based on its extension."""
        suffix = archive_path.suffix.lower()

        if suffix == ".zip":
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif suffix in [".tar", ".gz", ".bz2", ".xz"] or ".tar." in archive_path.name.lower():
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
        else:
            raise ValueError(f"Unsupported archive format: {suffix}")
