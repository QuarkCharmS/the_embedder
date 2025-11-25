"""
Upload handlers for files, git repositories, and archives to Qdrant.

Classes:
- FileHandler: Upload single file (auto-detects archives)
- RepoHandler: Clone and upload git repository with smart sync
- ArchiveHandler: Extract and upload archive contents

See ARCHITECTURE.md for detailed flow and logic.
"""

import tempfile
import tarfile
import zipfile
import os
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
import pathspec
from tqdm import tqdm

from app.qdrant_chunker import file_to_qdrant_chunks
from app.qdrant_uploader import upload_chunks_to_qdrant
from app.git_utils import smart_git_clone, get_repo_name_from_url, GitCloneError
from app.qdrant_manager import QdrantManager
from app.embedder import Embedder
from app.project_analyzer import generate_project_metadata
from app.logger import get_logger

logger = get_logger(__name__)

# Color constants for terminal output
_GREEN = '\033[32m'
_YELLOW = '\033[33m'
_RED = '\033[31m'
_GRAY = '\033[90m'
_RESET = '\033[0m'
_BOLD = '\033[1m'

# Skip patterns for file processing
_SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.env', 'dist', 'build', '.cache', '.pytest_cache',
    '.mypy_cache', '.tox', 'htmlcov', '.coverage', '.egg-info',
    'site-packages'
}

_SKIP_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
    '.bin', '.class', '.o', '.a', '.obj', '.lib'
}

_SKIP_NAMES = {
    '.DS_Store', 'Thumbs.db', '.gitignore', '.gitkeep',
    'PKG-INFO', 'dependency_links.txt', 'top_level.txt',
    'SOURCES.txt', 'requires.txt'
}


def load_gitignore_patterns(directory: Path):
    """Load and parse .gitignore patterns from a directory."""
    gitignore_path = directory / ".gitignore"
    if not gitignore_path.exists():
        return None

    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            patterns = f.read().splitlines()
        patterns = [p for p in patterns if p.strip() and not p.strip().startswith('#')]
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    except IOError as e:
        logger.warning("Could not parse .gitignore: %s", e)
        return None


def is_archive_file(file_path: str) -> bool:
    """Check if a file is an archive based on its extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    archive_extensions = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2', '.txz'}

    if suffix in archive_extensions:
        return True

    if len(path.suffixes) >= 2:
        double_suffix = ''.join(path.suffixes[-2:]).lower()
        if double_suffix in {'.tar.gz', '.tar.bz2', '.tar.xz'}:
            return True

    return False


def _should_skip_file(file_path: Path, directory: Path, gitignore_spec) -> bool:
    """Check if file should be skipped based on common patterns."""
    parts = file_path.parts

    if gitignore_spec:
        try:
            rel_path = file_path.relative_to(directory)
            rel_path_str = str(rel_path).replace(os.sep, '/')
            if gitignore_spec.match_file(rel_path_str):
                return True
        except ValueError:
            pass

    if '.git' in parts or '__pycache__' in parts:
        return True

    if any(skip_dir in parts for skip_dir in _SKIP_DIRS):
        return True

    if file_path.suffix.lower() in _SKIP_EXTENSIONS:
        return True

    if file_path.name in _SKIP_NAMES:
        return True

    return False


def _extract_archive(archive_path: Path, extract_to: Path):
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


def _collect_files_to_process(directory: Path, gitignore_spec):
    """Collect all files that should be processed."""
    all_files = list(directory.rglob("*"))
    files_to_process = []
    skipped_files = []

    for f in all_files:
        if f.is_file():
            if _should_skip_file(f, directory, gitignore_spec):
                skipped_files.append(str(f.name))
            else:
                files_to_process.append((f, f.relative_to(directory)))

    return files_to_process, skipped_files


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file using streaming for memory efficiency."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def _hash_file_for_parallel(args):
    """
    Top-level function for parallel hash computation (must be picklable).

    Args:
        args: Tuple of (file_path, rel_path, repo_name, use_prefix, collection_name)

    Returns:
        Tuple of (file_path, full_relative_path, file_hash)
    """
    file_path, rel_path, repo_name, use_prefix, collection_name = args

    try:
        full_relative_path = f"{repo_name}/{rel_path}" if use_prefix else file_path.name
        file_hash = _compute_file_hash(file_path)
        return file_path, full_relative_path, file_hash, None
    except Exception as e:
        return file_path, None, None, str(e)


def _process_files_batch(file_handler, files_to_process, repo_name, collection_name,
                         embedding_model, api_token, debug_level, use_prefix,
                         qdrant_host="localhost", qdrant_port=6333):
    """
    Intelligently process files with hash-based change detection and streaming upload.

    Three-phase approach:
    1. Check file status (hash comparison) - identify new, modified, unchanged, deleted
    2. Delete old chunks for modified and deleted files
    3. Chunk and upload in streaming fashion:
       - Chunk files in parallel (4 workers)
       - Accumulate chunks up to 1000
       - Upload batch, flush, continue
       - Embeds in batches of 10, uploads every 1000 points

    This prevents RAM exhaustion by never holding more than 1000 chunks in memory,
    while still maintaining efficient batch processing across multiple files.
    """
    current_file_paths = set()
    manager = QdrantManager(host=qdrant_host, port=qdrant_port)

    # Phase 1: Parallel hash computation (using processes for true parallelism)
    files_to_chunk = []
    files_unchanged = []
    files_to_delete = {}  # file_path -> point_ids for modified files

    logger.info("Hashing %s files in parallel", len(files_to_process))

    # Prepare arguments for parallel hashing
    hash_args = [
        (file_path, rel_path, repo_name, use_prefix, collection_name)
        for file_path, rel_path in files_to_process
    ]

    # Hash files in parallel using multiple CPU cores
    file_hashes = {}
    with ProcessPoolExecutor(max_workers=16) as executor:
        with tqdm(total=len(hash_args), desc="Hashing files", unit="file",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  disable=(debug_level != "VERBOSE")) as pbar:
            for file_path, full_relative_path, file_hash, error in executor.map(_hash_file_for_parallel, hash_args):
                if error:
                    logger.error("Error hashing %s: %s", file_path, error)
                elif file_hash:
                    file_hashes[full_relative_path] = (file_path, file_hash)
                    if use_prefix:
                        current_file_paths.add(full_relative_path)
                pbar.update(1)

    # Fetch existing files from Qdrant (hashes only, no point IDs to save memory)
    prefix = f"{repo_name}/" if use_prefix else ""
    remote_files = manager.get_all_file_hashes(collection_name, prefix, include_point_ids=False)

    # Build local files dictionary
    local_files = {full_relative_path: file_hash for full_relative_path, (_, file_hash) in file_hashes.items()}

    # Compare local vs remote (bulk comparison, in-memory)
    logger.info("Comparing local vs remote files")
    files_needing_deletion = []  # Files that need their chunks deleted (modified or deleted)

    with tqdm(total=len(local_files), desc="Comparing files", unit="file",
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
              disable=(debug_level != "VERBOSE")) as pbar:
        for full_relative_path, local_hash in local_files.items():
            file_path = file_hashes[full_relative_path][0]

            if full_relative_path not in remote_files:
                # New file
                status = "new"
                files_to_chunk.append((file_path, full_relative_path, status))
            else:
                remote_hash = remote_files[full_relative_path]

                if remote_hash != local_hash:
                    # Modified file - need to delete old chunks
                    status = "modified"
                    files_to_chunk.append((file_path, full_relative_path, status))
                    files_needing_deletion.append(full_relative_path)
                else:
                    # Unchanged file
                    files_unchanged.append((file_path, full_relative_path))

            pbar.update(1)

    # Find deleted files (exist in remote but not in local codebase)
    for remote_file_path in remote_files:
        if remote_file_path not in local_files:
            files_needing_deletion.append(remote_file_path)

    # Calculate stats for logging
    num_deleted = len(files_needing_deletion) - len([f for f in files_needing_deletion if f in local_files])
    num_modified = len(files_needing_deletion) - num_deleted

    logger.info("Files: %s new/modified, %s unchanged, %s to delete",
                len(files_to_chunk), len(files_unchanged), len(files_needing_deletion))

    # Phase 2: Delete old chunks for modified and deleted files (in batches to save memory)
    if files_needing_deletion:
        logger.info("Deleting old chunks for %s files (%s modified, %s deleted)",
                    len(files_needing_deletion), num_modified, num_deleted)

        # Delete files in batches of 100 to avoid accumulating millions of point IDs
        batch_size = 100
        for i in range(0, len(files_needing_deletion), batch_size):
            batch_files = files_needing_deletion[i:i+batch_size]

            # Fetch point IDs only for this batch
            batch_point_ids = []
            for file_path in batch_files:
                point_ids = manager.get_point_ids_for_file(collection_name, file_path)
                batch_point_ids.extend(point_ids)

            # Delete this batch
            if batch_point_ids:
                logger.info("Deleting batch of %s chunks from %s files",
                           len(batch_point_ids), len(batch_files))
                manager._delete_points(collection_name, batch_point_ids)

    # Phase 3: Chunk and upload in streaming fashion (merged Phase 2+4)
    accumulated_chunks = []
    file_chunk_counts = {}
    upload_threshold = 500  # Reduced to avoid timeouts (uploads in batches of 100 inside)

    if files_to_chunk:
        # Create embedder once
        embedder = Embedder(model_name=embedding_model, api_token=api_token)

        def chunk_file(file_data):
            """Chunk a single file."""
            file_path, full_relative_path, status = file_data
            try:
                chunks = FileHandler.chunk_file(
                    file_path=str(file_path),
                    embedding_model=embedding_model,
                    relative_path=full_relative_path,
                    debug_level=debug_level
                )
                return True, full_relative_path, status, chunks
            except Exception as e:
                logger.error("Error chunking %s: %s", file_path, e)
                return False, full_relative_path, status, None

        # Process files in parallel with streaming futures (constant memory)
        # Only keep max_pending futures in memory at once
        max_pending = 100  # Limit memory usage
        with ThreadPoolExecutor(max_workers=4) as executor:
            file_iter = iter(files_to_chunk)
            pending_futures = {}  # future -> file_data mapping

            # Submit initial batch
            for _ in range(min(max_pending, len(files_to_chunk))):
                try:
                    file_data = next(file_iter)
                    future = executor.submit(chunk_file, file_data)
                    pending_futures[future] = file_data
                except StopIteration:
                    break

            with tqdm(total=len(files_to_chunk), desc="Chunking & uploading", unit="file",
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                      disable=(debug_level != "VERBOSE")) as pbar:

                while pending_futures:
                    # Wait for at least one future to complete
                    done, _ = wait(pending_futures.keys(), return_when=FIRST_COMPLETED)

                    for future in done:
                        success, full_relative_path, status, chunks = future.result()

                        if success and chunks:
                            # Accumulate chunks
                            accumulated_chunks.extend(chunks)
                            file_chunk_counts[full_relative_path] = (status, len(chunks))

                            # Upload when we reach threshold
                            if len(accumulated_chunks) >= upload_threshold:
                                logger.info("Uploading batch of %s chunks", len(accumulated_chunks))
                                manager.upload_chunks(collection_name, accumulated_chunks, embedder, debug_level)
                                accumulated_chunks = []  # Flush

                        pbar.update(1)

                        # Remove completed future (allows garbage collection)
                        del pending_futures[future]

                    # Submit new jobs to maintain max_pending futures
                    while len(pending_futures) < max_pending:
                        try:
                            file_data = next(file_iter)
                            future = executor.submit(chunk_file, file_data)
                            pending_futures[future] = file_data
                        except StopIteration:
                            break

        # Upload any remaining chunks (< 500)
        if accumulated_chunks:
            logger.info("Uploading final batch of %s chunks", len(accumulated_chunks))
            manager.upload_chunks(collection_name, accumulated_chunks, embedder, debug_level)

    # Format results to match expected structure
    results = []

    # Add processed files (new/modified)
    for full_relative_path, (status, chunk_count) in file_chunk_counts.items():
        file_stats = {}
        if status == "new":
            file_stats = {'added': [(full_relative_path, chunk_count)]}
        else:  # modified
            file_stats = {'modified': [(full_relative_path, chunk_count)]}
        results.append((True, None, full_relative_path, file_stats))

    # Add unchanged files
    for file_path, full_relative_path in files_unchanged:
        file_stats = {'unchanged': [(full_relative_path, 0)]}
        results.append((True, file_path, full_relative_path, file_stats))

    return results, current_file_paths


def _aggregate_file_stats(results):
    """Aggregate statistics from file processing results."""
    stats = {
        'added': [],
        'modified': [],
        'unchanged': [],
        'deleted': [],
        'errors': []
    }

    successful = sum(1 for success, _, _, _ in results if success)

    for success, file_path, _, file_stats in results:
        if success and file_stats:
            stats['added'].extend(file_stats.get('added', []))
            stats['modified'].extend(file_stats.get('modified', []))
            stats['unchanged'].extend(file_stats.get('unchanged', []))
        elif not success:
            stats['errors'].append(str(file_path.name))

    return stats, successful


def _handle_project_metadata(file_handler, directory, repo_name, gitignore_spec,
                             collection_name, embedding_model, api_token, debug_level,
                             qdrant_host="localhost", qdrant_port=6333):
    """Generate and upload project metadata documents."""
    logger.info("Generating project metadata")
    stats = {'added': [], 'modified': [], 'errors': []}

    try:
        metadata_docs = generate_project_metadata(directory, repo_name, gitignore_spec)

        for title, content in metadata_docs:
            logger.info("Processing: %s", title)

            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.md', delete=False, encoding='utf-8'
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                file_stats = file_handler.handle(
                    file_path=tmp_path,
                    collection_name=collection_name,
                    embedding_model=embedding_model,
                    api_token=api_token,
                    relative_path=title,
                    debug_level=debug_level,
                    qdrant_host=qdrant_host,
                    qdrant_port=qdrant_port
                )

                if file_stats:
                    stats['added'].extend(file_stats.get('added', []))
                    stats['modified'].extend(file_stats.get('modified', []))

            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        logger.info("✓ Project metadata uploaded (%s documents)", len(metadata_docs))

    except Exception as e:
        logger.error("Error generating metadata: %s", e)
        stats['errors'].append(f"metadata_generation: {str(e)}")

    return stats


def _cleanup_deleted_files(collection_name, prefix, existing_files, current_file_paths,
                          qdrant_host="localhost", qdrant_port=6333):
    """Remove chunks for files that no longer exist."""
    stats = {'deleted': []}
    files_to_delete = []

    for file_path, (_, point_ids) in existing_files.items():
        if file_path not in current_file_paths:
            files_to_delete.append((file_path, point_ids, len(point_ids)))
            stats['deleted'].append((file_path, len(point_ids)))

    if files_to_delete:
        logger.info("Deleting %s file(s) that no longer exist in repo", len(files_to_delete))
        manager = QdrantManager(host=qdrant_host, port=qdrant_port)
        for file_path, point_ids, _ in files_to_delete:
            logger.info("Deleting: %s", file_path)
            manager._delete_points(collection_name, point_ids)
    else:
        logger.info("No files to delete")

    return stats


def _print_summary(stats):
    """Print a visual summary of changes with colors (like git status)."""
    # Count totals
    added_count = len(stats['added'])
    modified_count = len(stats['modified'])
    unchanged_count = len(stats['unchanged'])
    deleted_count = len(stats['deleted'])
    error_count = len(stats['errors'])
    skipped_count = len(stats.get('skipped', []))

    total_added_chunks = sum(chunks for _, chunks in stats['added'])
    total_modified_chunks = sum(chunks for _, chunks in stats['modified'])
    total_unchanged_chunks = sum(chunks for _, chunks in stats['unchanged'])
    total_deleted_chunks = sum(chunks for _, chunks in stats['deleted'])

    # Print header
    print(f"\n{_BOLD}{'='*70}{_RESET}")
    print(f"{_BOLD}Repository Sync Summary{_RESET}")
    print(f"{_BOLD}{'='*70}{_RESET}\n")

    # Print statistics overview
    if added_count > 0:
        print(f"{_GREEN}{_BOLD}++ {added_count} file(s) added{_RESET} ({total_added_chunks} chunks)")
    if modified_count > 0:
        print(f"{_YELLOW}{_BOLD}~  {modified_count} file(s) modified{_RESET} ({total_modified_chunks} chunks)")
    if deleted_count > 0:
        print(f"{_RED}{_BOLD}-- {deleted_count} file(s) deleted{_RESET} ({total_deleted_chunks} chunks)")
    if unchanged_count > 0:
        print(f"{_GRAY}=  {unchanged_count} file(s) unchanged{_RESET} ({total_unchanged_chunks} chunks)")
    if skipped_count > 0:
        print(f"{_GRAY}○  {skipped_count} file(s) skipped (build artifacts, .git, etc.){_RESET}")
    if error_count > 0:
        print(f"{_RED}{_BOLD}✗  {error_count} file(s) failed{_RESET}")

    # Print detailed file list if there are changes
    if added_count > 0:
        print(f"\n{_GREEN}{_BOLD}Added files:{_RESET}")
        for file, chunks in sorted(stats['added'])[:20]:
            print(f"{_GREEN}  ++ {file}{_RESET} ({chunks} chunks)")
        if added_count > 20:
            print(f"{_GRAY}  ... and {added_count - 20} more{_RESET}")

    if modified_count > 0:
        print(f"\n{_YELLOW}{_BOLD}Modified files:{_RESET}")
        for file, chunks in sorted(stats['modified'])[:20]:
            print(f"{_YELLOW}  ~  {file}{_RESET} ({chunks} chunks)")
        if modified_count > 20:
            print(f"{_GRAY}  ... and {modified_count - 20} more{_RESET}")

    if deleted_count > 0:
        print(f"\n{_RED}{_BOLD}Deleted files:{_RESET}")
        for file, chunks in sorted(stats['deleted'])[:20]:
            print(f"{_RED}  -- {file}{_RESET} ({chunks} chunks)")
        if deleted_count > 20:
            print(f"{_GRAY}  ... and {deleted_count - 20} more{_RESET}")

    if error_count > 0:
        print(f"\n{_RED}{_BOLD}Failed files:{_RESET}")
        for file in sorted(stats['errors'])[:20]:
            print(f"{_RED}  ✗  {file}{_RESET}")
        if error_count > 20:
            print(f"{_GRAY}  ... and {error_count - 20} more{_RESET}")

    # Print footer
    total_changes = added_count + modified_count + deleted_count
    if total_changes > 0:
        print(f"\n{_BOLD}Total changes: {total_changes} file(s){_RESET}")
    else:
        print(f"\n{_GRAY}No changes detected{_RESET}")

    print(f"{_BOLD}{'='*70}{_RESET}\n")


class FileHandler:
    """
    Handles single file uploads to Qdrant.

    This is the atomic unit - processes one file at a time.
    Agnostic to model type - caller determines model and API key.

    Smart archive detection: If the file is an archive (.zip, .tar, etc.),
    it automatically delegates to ArchiveHandler to extract and process all files.
    """

    @staticmethod
    def chunk_file(file_path: str, embedding_model: str, relative_path: str = None,
                   debug_level: str = "NONE"):
        """
        Chunk a single file without uploading.

        Returns list of chunks for the file.
        """
        chunks = file_to_qdrant_chunks(
            file_path=file_path,
            embedding_model=embedding_model,
            relative_path=relative_path,
            debug_level=debug_level
        )
        return chunks

    @staticmethod
    def handle(file_path: str, collection_name: str, embedding_model: str,
               api_token: str, relative_path: str = None, debug_level: str = "NONE",
               qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """
        Process and upload a single file to Qdrant.

        Smart archive detection: If the file is an archive, it will be extracted
        and all files within will be processed.
        """
        if is_archive_file(file_path):
            logger.info("Detected archive file: %s", file_path)
            logger.info("Auto-switching to archive mode to extract and process all files")
            archive_handler = ArchiveHandler()
            return archive_handler.handle(
                archive_path=file_path,
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level,
                qdrant_host=qdrant_host,
                qdrant_port=qdrant_port
            )

        logger.info("Processing file: %s", file_path)
        logger.info("Model: %s", embedding_model)

        logger.info("Chunking...")
        chunks = FileHandler.chunk_file(file_path, embedding_model, relative_path, debug_level)
        logger.info("Created %s chunks", len(chunks))

        logger.info("Uploading to collection '%s'", collection_name)
        stats = upload_chunks_to_qdrant(
            qdrant_chunks=chunks,
            collection_name=collection_name,
            embedding_model=embedding_model,
            api_token=api_token,
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port
        )
        logger.info("✓ Upload complete")

        return stats


class RepoHandler:
    """
    Handles git repository uploads.

    Clones repo, walks the file tree, and processes each file.
    Intelligently syncs with Qdrant:
    - Only uploads new/changed files (hash-based)
    - Deletes chunks for removed files
    """

    def __init__(self):
        self.file_handler = FileHandler()

    def handle(self, git_url: str, collection_name: str, embedding_model: str,
               api_token: str, debug_level: str = "NONE", git_token: str = None,
               qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """
        Clone a git repository and intelligently sync to Qdrant.

        Supports both remote URLs and local archives containing repos.
        Smart sync: Only uploads new/changed files, deletes removed files.
        """
        logger.info("Processing repository: %s", git_url)

        git_url_path = Path(git_url)
        if git_url_path.exists() and git_url_path.is_file() and is_archive_file(git_url):
            logger.info("Detected local archive containing repository")
            self._handle_local_repo_archive(
                git_url, collection_name, embedding_model, api_token, debug_level,
                qdrant_host, qdrant_port
            )
            return

        repo_name = get_repo_name_from_url(git_url)

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"

            logger.info("Cloning repository to %s", repo_path)
            try:
                smart_git_clone(
                    git_url=git_url,
                    destination=repo_path,
                    git_token=git_token
                )
            except GitCloneError as e:
                logger.error("Git Clone Failed: %s", e)
                raise

            logger.info("✓ Repository cloned successfully")

            stats = self._process_directory(
                repo_path, repo_name, collection_name, embedding_model, api_token, debug_level,
                use_prefix=True, qdrant_host=qdrant_host, qdrant_port=qdrant_port
            )
            _print_summary(stats)

        logger.info("✓ Repository processing complete")

    def _handle_local_repo_archive(self, archive_path: str, collection_name: str,
                                   embedding_model: str, api_token: str, debug_level: str = "NONE",
                                   qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """Handle a local archive file containing a git repository."""
        archive_path = Path(archive_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            logger.info("Extracting archive")
            _extract_archive(archive_path, extract_path)
            logger.info("✓ Archive extracted")

            repo_dirs = []
            for root, dirs, _ in os.walk(extract_path):
                if '.git' in dirs:
                    repo_path = Path(root)
                    repo_name = repo_path.name
                    repo_dirs.append((repo_name, repo_path))
                    logger.info("Found repository: %s", repo_name)

            if not repo_dirs:
                raise ValueError(
                    "No git repository found in archive. "
                    "The archive must contain a directory with a .git folder. "
                    "For non-repo archives, use 'upload archive' instead."
                )

            for repo_name, repo_path in repo_dirs:
                logger.info("Processing repository: %s", repo_name)
                stats = self._process_directory(
                    repo_path, repo_name, collection_name, embedding_model, api_token, debug_level,
                    use_prefix=True, qdrant_host=qdrant_host, qdrant_port=qdrant_port
                )
                _print_summary(stats)

            logger.info("✓ Repository processing complete")

    def _process_directory(self, directory: Path, repo_name: str, collection_name: str,
                          embedding_model: str, api_token: str, debug_level: str = "NONE",
                          use_prefix: bool = True, qdrant_host: str = "localhost",
                          qdrant_port: int = 6333):
        """
        Walk directory tree and process all files in parallel with deletion detection.

        Smart sync behavior:
        - Only uploads new/changed files (hash comparison)
        - For repos (use_prefix=True): Deletes chunks for files that no longer exist
        - For archives (use_prefix=False): No deletion (archives are standalone collections)
        """
        stats = {
            'added': [],
            'modified': [],
            'unchanged': [],
            'deleted': [],
            'errors': [],
            'skipped': []
        }

        prefix = f"{repo_name}/" if use_prefix else ""

        gitignore_spec = load_gitignore_patterns(directory)
        if gitignore_spec:
            logger.info("Found .gitignore, respecting ignore patterns")

        # Get existing files from Qdrant if this is a repo
        existing_files = {}
        if use_prefix:
            manager = QdrantManager(host=qdrant_host, port=qdrant_port)
            if manager.collection_exists(collection_name):
                logger.info("Checking for deleted files with prefix '%s'", prefix)
                existing_files = manager._get_files_by_prefix(collection_name, prefix)
                logger.info("Found %s existing file(s) in collection with prefix", len(existing_files))

        # Collect files to process
        files_to_process, skipped = _collect_files_to_process(directory, gitignore_spec)
        stats['skipped'] = skipped
        logger.info("Found %s files in source", len(files_to_process))

        # Process files in parallel
        results, current_file_paths = _process_files_batch(
            self.file_handler, files_to_process, repo_name, collection_name,
            embedding_model, api_token, debug_level, use_prefix,
            qdrant_host, qdrant_port
        )

        # Aggregate results
        file_stats, successful = _aggregate_file_stats(results)
        stats.update(file_stats)
        logger.info("Successfully processed %s/%s files", successful, len(files_to_process))

        # Handle project metadata for repos
        if use_prefix:
            metadata_stats = _handle_project_metadata(
                self.file_handler, directory, repo_name, gitignore_spec,
                collection_name, embedding_model, api_token, debug_level
            )
            stats['added'].extend(metadata_stats['added'])
            stats['modified'].extend(metadata_stats['modified'])
            stats['errors'].extend(metadata_stats['errors'])

        # Cleanup deleted files for repos
        if use_prefix and existing_files:
            delete_stats = _cleanup_deleted_files(
                collection_name, prefix, existing_files, current_file_paths,
                qdrant_host, qdrant_port
            )
            stats['deleted'] = delete_stats['deleted']

        return stats


class ArchiveHandler:
    """
    Handles archive file uploads (.zip, .tar, .tar.gz, etc).

    Extracts archive to temp directory and delegates to RepoHandler logic.
    Agnostic to model type - caller determines model and API key.
    """

    def __init__(self):
        self.repo_handler = RepoHandler()

    def handle(self, archive_path: str, collection_name: str, embedding_model: str,
               api_token: str, debug_level: str = "NONE",
               qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """Extract archive and upload all files to Qdrant."""
        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        logger.info("Processing archive: %s", archive_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            logger.info("Extracting to %s", extract_path)
            _extract_archive(archive_path, extract_path)
            logger.info("Extraction complete")

            self.repo_handler._process_directory(
                directory=extract_path,
                repo_name=None,
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level,
                use_prefix=False,
                qdrant_host=qdrant_host,
                qdrant_port=qdrant_port
            )

        logger.info("✓ Archive processing complete")
