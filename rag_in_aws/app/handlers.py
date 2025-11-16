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
        # Filter out comments and empty lines
        patterns = [p for p in patterns if p.strip() and not p.strip().startswith('#')]
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    except Exception as e:
        print(f"Warning: Could not parse .gitignore: {e}")
        return None


def is_archive_file(file_path: str) -> bool:
    """
    Check if a file is an archive based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        True if file is an archive, False otherwise
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    # Check for common archive extensions
    archive_extensions = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2', '.txz'}

    # Also check for .tar.gz, .tar.bz2, .tar.xz patterns
    if suffix in archive_extensions:
        return True

    # Check for double extensions like .tar.gz
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
        # Smart archive detection - delegate to ArchiveHandler if it's an archive
        if is_archive_file(file_path):
            print(f"Detected archive file: {file_path}")
            print(f"Auto-switching to archive mode to extract and process all files...")
            archive_handler = ArchiveHandler()
            archive_handler.handle(
                archive_path=file_path,
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level
            )
            return

        # Regular file processing
        print(f"Processing file: {file_path}")
        print(f"  Model: {embedding_model}")

        # Chunk the file with relative path
        print(f"  Chunking...")
        chunks = file_to_qdrant_chunks(
            file_path=file_path,
            embedding_model=embedding_model,
            relative_path=relative_path,
            debug_level=debug_level
        )
        print(f"  Created {len(chunks)} chunks")

        # Upload to Qdrant
        print(f"  Uploading to collection '{collection_name}'...")
        stats = upload_chunks_to_qdrant(
            qdrant_chunks=chunks,
            collection_name=collection_name,
            embedding_model=embedding_model,
            api_token=api_token
        )
        print(f"  ✓ Upload complete")

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
        print(f"Processing repository: {git_url}")

        # Check if git_url is a local archive file containing a repo
        git_url_path = Path(git_url)
        if git_url_path.exists() and git_url_path.is_file() and is_archive_file(git_url):
            print(f"Detected local archive containing repository")
            self._handle_local_repo_archive(git_url, collection_name, embedding_model, api_token, debug_level)
            return

        # Extract repo name from URL
        repo_name = get_repo_name_from_url(git_url)

        # Create temp directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"

            # Smart clone with auto-detection and fallback
            print(f"Cloning repository to {repo_path}...")
            try:
                smart_git_clone(
                    git_url=git_url,
                    destination=repo_path,
                    git_token=git_token
                )
            except GitCloneError as e:
                print(f"\n❌ Git Clone Failed:")
                print(f"{e}")
                raise

            print("✓ Repository cloned successfully")

            # Walk the repository and process files with deletion detection
            stats = self._process_directory(repo_path, repo_name, collection_name, embedding_model, api_token, debug_level)
            self._print_summary(stats)

        print(f"✓ Repository processing complete")

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

            # Extract archive
            print(f"Extracting archive...")
            self._extract_archive(archive_path, extract_path)
            print("✓ Archive extracted")

            # Find directories with .git
            repo_dirs = []
            for root, dirs, files in os.walk(extract_path):
                if '.git' in dirs or '.git' in files:
                    repo_path = Path(root)
                    repo_name = repo_path.name
                    repo_dirs.append((repo_name, repo_path))
                    print(f"Found repository: {repo_name}")

            if not repo_dirs:
                raise ValueError(
                    f"No git repository found in archive. "
                    f"The archive must contain a directory with a .git folder. "
                    f"For non-repo archives, use 'upload archive' instead."
                )

            # Process each repo found
            for repo_name, repo_path in repo_dirs:
                print(f"\nProcessing repository: {repo_name}")
                stats = self._process_directory(repo_path, repo_name, collection_name, embedding_model, api_token, debug_level)
                self._print_summary(stats)

            print(f"✓ Repository processing complete")

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

        # Load .gitignore patterns if present
        gitignore_spec = load_gitignore_patterns(directory)
        if gitignore_spec:
            print(f"Found .gitignore, respecting ignore patterns")

        # Get existing files from Qdrant (only for repos with prefix)
        existing_files = {}
        if use_prefix:  # Only check for deletions in repos
            manager = QdrantManager()
            if manager.collection_exists(collection_name):
                print(f"Checking for deleted files with prefix '{prefix}'...")
                existing_files = manager._get_files_by_prefix(collection_name, prefix)
                print(f"Found {len(existing_files)} existing file(s) in collection with prefix")

        # Walk all files in directory and filter
        all_files = list(directory.rglob("*"))

        # Filter function to skip unwanted files
        def should_skip_file(file_path: Path) -> bool:
            """Check if file should be skipped based on common patterns."""
            path_str = str(file_path)
            parts = file_path.parts

            # Check .gitignore patterns first
            if gitignore_spec:
                # Get relative path from directory root
                try:
                    rel_path = file_path.relative_to(directory)
                    # pathspec expects forward slashes
                    rel_path_str = str(rel_path).replace(os.sep, '/')
                    if gitignore_spec.match_file(rel_path_str):
                        return True
                except ValueError:
                    pass  # file_path not relative to directory

            # Skip .git directory contents
            if '.git' in parts:
                return True

            # Skip __pycache__ directories
            if '__pycache__' in parts:
                return True

            # Skip common build/cache directories
            skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                        '.env', 'dist', 'build', '.cache', '.pytest_cache',
                        '.mypy_cache', '.tox', 'htmlcov', '.coverage', '.egg-info',
                        'site-packages'}
            if any(skip_dir in parts for skip_dir in skip_dirs):
                return True

            # Skip binary file extensions
            skip_extensions = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
                             '.bin', '.class', '.o', '.a', '.obj', '.lib'}
            if file_path.suffix.lower() in skip_extensions:
                return True

            # Skip common metadata files
            skip_names = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitkeep',
                         'PKG-INFO', 'dependency_links.txt', 'top_level.txt',
                         'SOURCES.txt', 'requires.txt'}
            if file_path.name in skip_names:
                return True

            return False

        # Filter files
        files_to_process = []
        for f in all_files:
            if f.is_file():
                if should_skip_file(f):
                    stats['skipped'].append(str(f.name))
                else:
                    files_to_process.append((f, f.relative_to(directory)))

        print(f"Found {len(files_to_process)} files in source")

        # Track which files we're processing (only needed for repos with deletion detection)
        current_file_paths = set()

        def process_file(file_data):
            file_path, rel_path = file_data
            try:
                # For repos: use full path with repo name prefix
                # For archives: use only the filename
                if use_prefix:
                    full_relative_path = f"{repo_name}/{rel_path}"
                else:
                    # Just use the filename for archives
                    full_relative_path = file_path.name

                if use_prefix:  # Only track for deletion detection
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
                print(f"  ✗ Error processing {file_path}: {e}")
                return False, file_path, None, None

        # Process files in parallel with 4 workers
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_file, files_to_process))

        # Aggregate stats from all file uploads
        successful = sum(1 for success, _, _, _ in results if success)
        for success, file_path, rel_path, file_stats in results:
            if success and file_stats:
                # Merge file stats into overall stats
                for file, chunks in file_stats.get('added', []):
                    stats['added'].append((file, chunks))
                for file, chunks in file_stats.get('modified', []):
                    stats['modified'].append((file, chunks))
                for file, chunks in file_stats.get('unchanged', []):
                    stats['unchanged'].append((file, chunks))
            elif not success:
                stats['errors'].append(str(file_path.name))

        print(f"Successfully processed {successful}/{len(files_to_process)} files")

        # Generate and upload project metadata (only for repos)
        if use_prefix:
            print(f"\nGenerating project metadata...")
            try:
                metadata_docs = generate_project_metadata(directory, repo_name, gitignore_spec)

                # Process each metadata document using FileHandler
                # This way they get properly chunked like regular files
                for title, content in metadata_docs:
                    print(f"  Processing: {title}")

                    # Write metadata to temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    try:
                        # Process using FileHandler (handles chunking automatically)
                        file_stats = self.file_handler.handle(
                            file_path=tmp_path,
                            collection_name=collection_name,
                            embedding_model=embedding_model,
                            api_token=api_token,
                            relative_path=title,
                            debug_level=debug_level
                        )

                        # Track stats
                        if file_stats:
                            for file, chunks in file_stats.get('added', []):
                                stats['added'].append((title, chunks))
                            for file, chunks in file_stats.get('modified', []):
                                stats['modified'].append((title, chunks))

                    finally:
                        # Clean up temp file
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass

                print(f"  ✓ Project metadata uploaded ({len(metadata_docs)} documents)")

            except Exception as e:
                print(f"  ✗ Error generating metadata: {e}")
                # Don't fail the whole upload if metadata fails
                stats['errors'].append(f"metadata_generation: {str(e)}")

        # Delete files that no longer exist (only for repos)
        if use_prefix and existing_files:
            files_to_delete = []
            for file_path, (file_hash, point_ids) in existing_files.items():
                if file_path not in current_file_paths:
                    files_to_delete.append((file_path, point_ids, len(point_ids)))
                    stats['deleted'].append((file_path, len(point_ids)))

            if files_to_delete:
                print(f"\nDeleting {len(files_to_delete)} file(s) that no longer exist in repo...")
                manager = QdrantManager()
                for file_path, point_ids, _ in files_to_delete:
                    print(f"  - Deleting: {file_path}")
                    manager._delete_points(collection_name, point_ids)
            else:
                print("No files to delete")

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

        print(f"Processing archive: {archive_path}")

        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = Path(temp_dir) / "extracted"
            extract_path.mkdir()

            # Extract based on file type
            print(f"Extracting to {extract_path}...")
            self._extract_archive(archive_path, extract_path)
            print("Extraction complete")

            # Process extracted files - use only filenames, no path prefix
            # Archives are treated as collections of standalone files
            self.repo_handler._process_directory(
                directory=extract_path,
                repo_name=None,  # Not used when use_prefix=False
                collection_name=collection_name,
                embedding_model=embedding_model,
                api_token=api_token,
                debug_level=debug_level,
                use_prefix=False  # Archives use only filenames, not full paths
            )

        print(f"✓ Archive processing complete")

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
