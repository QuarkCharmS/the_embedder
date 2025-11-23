"""
Upload handlers for RAG backend.

FileHandler: Processes single files (with smart archive detection)
RepoHandler: Clones and processes git repositories
ArchiveHandler: Extracts and processes archive files (.zip, .tar, .tar.gz)
"""

import tempfile
import shutil
import tarfile
import zipfile
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import pathspec

from app.qdrant_chunker import file_to_qdrant_chunks
from app.qdrant_uploader import upload_chunks_to_qdrant
from app.git_utils import smart_git_clone, get_repo_name_from_url, GitCloneError
from app.qdrant_manager import QdrantManager
from app.project_analyzer import generate_project_metadata
from app.embedder import Embedder
from app.logger import get_logger

logger = get_logger(__name__)


def load_gitignore_patterns(directory: Path):
    """
    Load and parse .gitignore patterns from a directory.

    Args:
        directory: Root directory to search for .gitignore

    Returns:
        pathspec.PathSpec object or None if no .gitignore found
    """
    gitignore_path = directory / ".gitignore"
    if not gitignore_path.exists():
        return None

    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            patterns = f.read().splitlines()
        patterns = [p for p in patterns if p.strip() and not p.strip().startswith('#')]
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    except Exception as e:
        logger.warning(f"Could not parse .gitignore: {e}")
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


class FileHandler:
    """
    Handles single file uploads to Qdrant.

    This is the atomic unit - processes one file at a time.
    Agnostic to model type - caller determines model and API key.

    Smart archive detection: If the file is an archive (.zip, .tar, etc.),
    it automatically delegates to ArchiveHandler to extract and process all files.
    """

    @staticmethod
    def handle(file_path: str, collection_name: str, embedding_model: str, api_token: str, relative_path: str = None, debug_level: str = "NONE"):
        """
        Process and upload a single file to Qdrant.

        Smart archive detection: If the file is an archive, it will be extracted
        and all files within will be processed.

        Args:
            file_path: Path to the file
            collection_name: Qdrant collection name
            embedding_model: Embedding model to use (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for the embedding service
            relative_path: Optional relative path to store (defaults to filename)
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
        """
        if is_archive_file(file_path):
            logger.info(f"Detected archive file: {file_path}")
            logger.info("Auto-switching to archive mode to extract and process all files")
            archive_handler = ArchiveHandler()
            archive_handler.handle(
                archive_path=file_path,
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level
            )
            return

        logger.info(f"Processing file: {file_path}")
        logger.info(f"Model: {embedding_model}")

        logger.info("Chunking...")
        chunks = file_to_qdrant_chunks(
            file_path=file_path,
            embedding_model=embedding_model,
            relative_path=relative_path,
            debug_level=debug_level
        )
        logger.info(f"Created {len(chunks)} chunks")

        logger.info(f"Uploading to collection '{collection_name}'")
        stats = upload_chunks_to_qdrant(
            qdrant_chunks=chunks,
            collection_name=collection_name,
            embedding_model=embedding_model,
            api_token=api_token
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

    def handle(self, git_url: str, collection_name: str, embedding_model: str, api_token: str,
               debug_level: str = "NONE", git_token: str = None):
        """
        Clone a git repository and intelligently sync to Qdrant.

        Supports both remote URLs and local archives containing repos:
        - Remote URLs: Clones via git
        - Local archives: Extracts and processes repos with .git directory

        Smart sync:
        - Only uploads new/changed files (hash comparison)
        - Deletes chunks for files that were removed from repo

        Smart authentication (for remote URLs):
        - Tries to clone without auth first (public repos)
        - For SSH: Auto-detects keys from ~/.ssh/ (id_rsa, id_ed25519, etc.)
        - For HTTPS: Uses git_token if provided
        - Container-friendly: finds mounted SSH keys automatically

        Args:
            git_url: Git repository URL or path to local archive
                     Remote: https://github.com/user/repo.git or git@github.com:user/repo.git
                     Local: /path/to/repo.zip (must contain .git directory)
            collection_name: Qdrant collection name
            embedding_model: Embedding model to use (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for the embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
            git_token: Personal access token for private HTTPS repos (optional, remote only)
        """
        logger.info(f"Processing repository: {git_url}")

        git_url_path = Path(git_url)
        if git_url_path.exists() and git_url_path.is_file() and is_archive_file(git_url):
            logger.info("Detected local archive containing repository")
            self._handle_local_repo_archive(git_url, collection_name, embedding_model, api_token, debug_level)
            return

        repo_name = get_repo_name_from_url(git_url)

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"

            logger.info(f"Cloning repository to {repo_path}")
            try:
                smart_git_clone(
                    git_url=git_url,
                    destination=repo_path,
                    git_token=git_token
                )
            except GitCloneError as e:
                logger.error(f"Git Clone Failed: {e}")
                raise

            logger.info("✓ Repository cloned successfully")

            stats = self._process_directory(repo_path, repo_name, collection_name, embedding_model, api_token, debug_level)
            self._print_summary(stats)

        logger.info("✓ Repository processing complete")

    def _handle_local_repo_archive(self, archive_path: str, collection_name: str, embedding_model: str, api_token: str, debug_level: str = "NONE"):
        """
        Handle a local archive file containing a git repository.

        Extracts the archive and looks for .git directories to identify repos.

        Args:
            archive_path: Path to archive file (.zip, .tar, .tar.gz)
            collection_name: Qdrant collection name
            embedding_model: Embedding model to use (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for the embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
        """
        archive_path = Path(archive_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            logger.info("Extracting archive")
            self._extract_archive(archive_path, extract_path)
            logger.info("✓ Archive extracted")

            repo_dirs = []
            for root, dirs, files in os.walk(extract_path):
                if '.git' in dirs or '.git' in files:
                    repo_path = Path(root)
                    repo_name = repo_path.name
                    repo_dirs.append((repo_name, repo_path))
                    logger.info(f"Found repository: {repo_name}")

            if not repo_dirs:
                raise ValueError(
                    f"No git repository found in archive. "
                    f"The archive must contain a directory with a .git folder. "
                    f"For non-repo archives, use 'upload archive' instead."
                )

            for repo_name, repo_path in repo_dirs:
                logger.info(f"Processing repository: {repo_name}")
                stats = self._process_directory(repo_path, repo_name, collection_name, embedding_model, api_token, debug_level)
                self._print_summary(stats)

            logger.info("✓ Repository processing complete")

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

    def _process_directory(self, directory: Path, repo_name: str, collection_name: str, embedding_model: str, api_token: str, debug_level: str = "NONE", use_prefix: bool = True):
        """
        Walk directory tree and process all files in parallel with deletion detection.

        Smart sync behavior:
        - Only uploads new/changed files (hash comparison)
        - For repos (use_prefix=True): Deletes chunks for files that no longer exist
        - For archives (use_prefix=False): No deletion (archives are standalone collections)

        Args:
            directory: Directory path to walk
            repo_name: Name of the repository (for path prefixing when use_prefix=True)
            collection_name: Qdrant collection name
            embedding_model: Embedding model to use (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for the embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
            use_prefix: If True, prefix paths with repo_name and enable deletion detection.
                       If False, use only filename (archives, no deletion detection).

        Returns:
            Dict with stats: {'added': [], 'modified': [], 'unchanged': [], 'deleted': [], 'errors': []}
        """
        # Initialize stats tracking
        stats = {
            'added': [],
            'modified': [],
            'unchanged': [],
            'deleted': [],
            'errors': [],
            'skipped': []
        }

        # Get prefix for querying existing files (only for repos)
        prefix = f"{repo_name}/" if use_prefix else ""

        gitignore_spec = load_gitignore_patterns(directory)
        if gitignore_spec:
            logger.info("Found .gitignore, respecting ignore patterns")

        existing_files = {}
        if use_prefix:
            manager = QdrantManager()
            if manager.collection_exists(collection_name):
                logger.info(f"Checking for deleted files with prefix '{prefix}'")
                existing_files = manager._get_files_by_prefix(collection_name, prefix)
                logger.info(f"Found {len(existing_files)} existing file(s) in collection with prefix")

        all_files = list(directory.rglob("*"))

        def should_skip_file(file_path: Path) -> bool:
            """Check if file should be skipped based on common patterns."""
            path_str = str(file_path)
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

            skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                        '.env', 'dist', 'build', '.cache', '.pytest_cache',
                        '.mypy_cache', '.tox', 'htmlcov', '.coverage', '.egg-info',
                        'site-packages'}
            if any(skip_dir in parts for skip_dir in skip_dirs):
                return True

            skip_extensions = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
                             '.bin', '.class', '.o', '.a', '.obj', '.lib'}
            if file_path.suffix.lower() in skip_extensions:
                return True

            skip_names = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitkeep',
                         'PKG-INFO', 'dependency_links.txt', 'top_level.txt',
                         'SOURCES.txt', 'requires.txt'}
            if file_path.name in skip_names:
                return True

            return False

        files_to_process = []
        for f in all_files:
            if f.is_file():
                if should_skip_file(f):
                    stats['skipped'].append(str(f.name))
                else:
                    files_to_process.append((f, f.relative_to(directory)))

        logger.info(f"Found {len(files_to_process)} files in source")

        current_file_paths = set()

        def process_file(file_data):
            file_path, rel_path = file_data
            try:
                if use_prefix:
                    full_relative_path = f"{repo_name}/{rel_path}"
                else:
                    full_relative_path = file_path.name

                if use_prefix:
                    current_file_paths.add(full_relative_path)

                file_stats = self.file_handler.handle(
                    file_path=str(file_path),
                    collection_name=collection_name,
                    embedding_model=embedding_model,
                    api_token=api_token,
                    relative_path=full_relative_path,
                    debug_level=debug_level
                )
                return True, file_path, full_relative_path, file_stats
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                return False, file_path, None, None

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_file, files_to_process))

        successful = sum(1 for success, _, _, _ in results if success)
        for success, file_path, rel_path, file_stats in results:
            if success and file_stats:
                for file, chunks in file_stats.get('added', []):
                    stats['added'].append((file, chunks))
                for file, chunks in file_stats.get('modified', []):
                    stats['modified'].append((file, chunks))
                for file, chunks in file_stats.get('unchanged', []):
                    stats['unchanged'].append((file, chunks))
            elif not success:
                stats['errors'].append(str(file_path.name))

        logger.info(f"Successfully processed {successful}/{len(files_to_process)} files")

        if use_prefix:
            logger.info("Generating project metadata")
            try:
                metadata_docs = generate_project_metadata(directory, repo_name, gitignore_spec)

                for title, content in metadata_docs:
                    logger.info(f"Processing: {title}")

                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    try:
                        file_stats = self.file_handler.handle(
                            file_path=tmp_path,
                            collection_name=collection_name,
                            embedding_model=embedding_model,
                            api_token=api_token,
                            relative_path=title,
                            debug_level=debug_level
                        )

                        if file_stats:
                            for file, chunks in file_stats.get('added', []):
                                stats['added'].append((title, chunks))
                            for file, chunks in file_stats.get('modified', []):
                                stats['modified'].append((title, chunks))

                    finally:
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass

                logger.info(f"✓ Project metadata uploaded ({len(metadata_docs)} documents)")

            except Exception as e:
                logger.error(f"Error generating metadata: {e}")
                stats['errors'].append(f"metadata_generation: {str(e)}")

        if use_prefix and existing_files:
            files_to_delete = []
            for file_path, (file_hash, point_ids) in existing_files.items():
                if file_path not in current_file_paths:
                    files_to_delete.append((file_path, point_ids, len(point_ids)))
                    stats['deleted'].append((file_path, len(point_ids)))

            if files_to_delete:
                logger.info(f"Deleting {len(files_to_delete)} file(s) that no longer exist in repo")
                manager = QdrantManager()
                for file_path, point_ids, _ in files_to_delete:
                    logger.info(f"Deleting: {file_path}")
                    manager._delete_points(collection_name, point_ids)
            else:
                logger.info("No files to delete")

        return stats

    def _print_summary(self, stats):
        """
        Print a visual summary of changes with colors (like git status).

        Args:
            stats: Dict with 'added', 'modified', 'unchanged', 'deleted', 'errors' lists
        """
        # ANSI color codes
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        RED = '\033[31m'
        BLUE = '\033[34m'
        GRAY = '\033[90m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

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
        print(f"\n{BOLD}{'='*70}{RESET}")
        print(f"{BOLD}Repository Sync Summary{RESET}")
        print(f"{BOLD}{'='*70}{RESET}\n")

        # Print statistics overview
        if added_count > 0:
            print(f"{GREEN}{BOLD}++ {added_count} file(s) added{RESET} ({total_added_chunks} chunks)")
        if modified_count > 0:
            print(f"{YELLOW}{BOLD}~  {modified_count} file(s) modified{RESET} ({total_modified_chunks} chunks)")
        if deleted_count > 0:
            print(f"{RED}{BOLD}-- {deleted_count} file(s) deleted{RESET} ({total_deleted_chunks} chunks)")
        if unchanged_count > 0:
            print(f"{GRAY}=  {unchanged_count} file(s) unchanged{RESET} ({total_unchanged_chunks} chunks)")
        if skipped_count > 0:
            print(f"{GRAY}○  {skipped_count} file(s) skipped (build artifacts, .git, etc.){RESET}")
        if error_count > 0:
            print(f"{RED}{BOLD}✗  {error_count} file(s) failed{RESET}")

        # Print detailed file list if there are changes
        if added_count > 0:
            print(f"\n{GREEN}{BOLD}Added files:{RESET}")
            for file, chunks in sorted(stats['added'])[:20]:  # Limit to first 20
                print(f"{GREEN}  ++ {file}{RESET} ({chunks} chunks)")
            if added_count > 20:
                print(f"{GRAY}  ... and {added_count - 20} more{RESET}")

        if modified_count > 0:
            print(f"\n{YELLOW}{BOLD}Modified files:{RESET}")
            for file, chunks in sorted(stats['modified'])[:20]:
                print(f"{YELLOW}  ~  {file}{RESET} ({chunks} chunks)")
            if modified_count > 20:
                print(f"{GRAY}  ... and {modified_count - 20} more{RESET}")

        if deleted_count > 0:
            print(f"\n{RED}{BOLD}Deleted files:{RESET}")
            for file, chunks in sorted(stats['deleted'])[:20]:
                print(f"{RED}  -- {file}{RESET} ({chunks} chunks)")
            if deleted_count > 20:
                print(f"{GRAY}  ... and {deleted_count - 20} more{RESET}")

        if error_count > 0:
            print(f"\n{RED}{BOLD}Failed files:{RESET}")
            for file in sorted(stats['errors'])[:20]:
                print(f"{RED}  ✗  {file}{RESET}")
            if error_count > 20:
                print(f"{GRAY}  ... and {error_count - 20} more{RESET}")

        # Print footer
        total_changes = added_count + modified_count + deleted_count
        if total_changes > 0:
            print(f"\n{BOLD}Total changes: {total_changes} file(s){RESET}")
        else:
            print(f"\n{GRAY}No changes detected{RESET}")

        print(f"{BOLD}{'='*70}{RESET}\n")


class ArchiveHandler:
    """
    Handles archive file uploads (.zip, .tar, .tar.gz, etc).

    Extracts archive to temp directory and delegates to RepoHandler logic.
    Agnostic to model type - caller determines model and API key.
    """

    def __init__(self):
        self.repo_handler = RepoHandler()

    def handle(self, archive_path: str, collection_name: str, embedding_model: str, api_token: str, debug_level: str = "NONE"):
        """
        Extract archive and upload all files to Qdrant.

        Args:
            archive_path: Path to archive file
            collection_name: Qdrant collection name
            embedding_model: Embedding model to use (e.g., "Qwen/Qwen3-Embedding-8B")
            api_token: API token for the embedding service
            debug_level: Debug level for chunker ("NONE" or "VERBOSE")
        """
        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        logger.info(f"Processing archive: {archive_path}")

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            logger.info(f"Extracting to {extract_path}")
            self._extract_archive(archive_path, extract_path)
            logger.info("Extraction complete")

            self.repo_handler._process_directory(
                directory=extract_path,
                repo_name=None,
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level,
                use_prefix=False
            )

        logger.info("✓ Archive processing complete")

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

        elif suffix in [".tar", ".gz", ".bz2", ".xz"] or ".tar." in archive_path.name:
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)

        else:
            raise ValueError(f"Unsupported archive format: {suffix}")
