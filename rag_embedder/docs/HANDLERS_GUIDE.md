# Handlers Guide

## Overview

`handlers.py` provides four handlers for uploading content to Qdrant RAG backend:
- **FileHandler**: Single files
- **RepoHandler**: Git repositories with intelligent incremental sync
- **ArchiveHandler**: Zip/tar archives
- **S3Handler**: S3 buckets and S3-compatible storage (AWS S3, MinIO, DigitalOcean Spaces, etc.)

## Architecture

```
FileHandler (atomic unit - processes single files)
    ↑ used by
RepoHandler (clones repos, intelligent sync, processes directories)
    ↑ used by
ArchiveHandler (extracts archives, delegates to RepoHandler)
S3Handler (downloads S3 buckets, delegates to RepoHandler)
```

## Handlers

### FileHandler

**Purpose**: Upload a single file to Qdrant

**Features**:
- Auto-detects if file is an archive and delegates to ArchiveHandler
- Supports 20+ file formats (PDF, DOCX, code files, markdown, etc.)
- Semantic chunking via `the_chunker` library
- Hash-based deduplication

**Usage**:
```python
from app.handlers import FileHandler

FileHandler.handle(
    file_path="/path/to/file.py",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_token",
    relative_path="file.py"
)
```

**Flow**:
1. Validates file exists
2. Checks if file is an archive (if yes, delegates to ArchiveHandler)
3. Chunks file using `file_to_qdrant_chunks()`
4. Uploads chunks to Qdrant with embeddings

### RepoHandler

**Purpose**: Clone git repository and upload all files with intelligent sync

**Features**:
- Smart git cloning (auto-detects SSH/HTTPS, handles private repos)
- Hash-based change detection (SHA256)
- Incremental sync: only processes new/modified files
- Deletion detection: removes files that no longer exist
- Parallel processing (16 workers for hashing, 4 for chunking)
- Respects .gitignore patterns
- Generates project metadata

**Usage**:
```python
from app.handlers import RepoHandler

handler = RepoHandler()
handler.handle(
    git_url="https://github.com/user/repo.git",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_token",
    git_token="github_token"  # Optional for private repos
)
```

**Flow**:
1. Clones repo to temp directory using `smart_git_clone()`
2. Calls `_process_directory()` with `use_prefix=True`
3. **Phase 1**: Parallel hash computation (16 CPU workers)
   - Computes SHA256 hash for each file
   - Compares with hashes stored in Qdrant
4. **Phase 2**: Deletes old chunks for modified/deleted files
5. **Phase 3**: Chunks and uploads new/modified files (4 thread workers)
6. Generates project metadata (optional)
7. Cleans up temp directory

**Sync Behavior**:
- **New files**: Upload with embeddings
- **Modified files** (hash changed): Delete old chunks, upload new
- **Unchanged files** (hash matches): Skip entirely (no processing)
- **Deleted files**: Remove chunks from Qdrant

### ArchiveHandler

**Purpose**: Extract and upload archive contents (.zip, .tar, .tar.gz, etc.)

**Features**:
- Supports multiple archive formats: .zip, .tar, .gz, .bz2, .xz, .tgz, .tbz2, .txz
- Extracts to temp directory
- Delegates to RepoHandler for processing
- Auto-cleanup

**Usage**:
```python
from app.handlers import ArchiveHandler

handler = ArchiveHandler()
handler.handle(
    archive_path="/path/to/archive.tar.gz",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_token"
)
```

**Flow**:
1. Validates archive exists
2. Extracts to temp directory using `_extract_archive()`
3. Delegates to `RepoHandler._process_directory()` with `use_prefix=False`
4. Cleans up temp directory

**Supported Formats**:
- ZIP: `.zip`
- TAR: `.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`
- Compressed: `.tgz`, `.tbz2`, `.txz`

### S3Handler (New)

**Purpose**: Download S3 bucket contents and upload to Qdrant

**Features**:
- Multi-auth support:
  - IAM roles (automatic for EC2/ECS/Lambda)
  - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
  - AWS profiles (~/.aws/credentials)
  - Explicit credentials via CLI
- Bucket prefixes for targeted downloads
- Pagination support for large buckets (>1000 objects)
- Custom S3 endpoints (MinIO, DigitalOcean Spaces, Wasabi, etc.)
- Incremental sync (hash-based deduplication)
- Smart filtering (respects skip patterns)

**Usage**:
```python
from app.handlers import S3Handler

handler = S3Handler()
handler.handle(
    bucket_name="my-bucket",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_token",
    prefix="docs/",  # Optional: only download this folder
    s3_endpoint="https://minio.example.com",  # Optional: custom endpoint
    aws_access_key_id="key",  # Optional: explicit credentials
    aws_secret_access_key="secret",
    aws_region="us-east-1"
)
```

**Flow**:
1. Parses S3 URI if provided (s3://bucket/prefix)
2. Creates boto3 S3 client with authentication
3. Downloads bucket contents to temp directory:
   - Uses paginator for large buckets
   - First pass: counts objects for progress bar
   - Second pass: downloads files preserving folder structure
   - Skips objects matching skip patterns
4. Delegates to `RepoHandler._process_directory()` with `use_prefix=True`
5. Uses bucket name as prefix in Qdrant (e.g., "my-bucket/file.py")
6. Cleans up temp directory

**S3 URI Format**:
```bash
# Bucket name only
s3://my-bucket

# With prefix
s3://my-bucket/docs/api/
```

**Authentication Methods** (in priority order):
1. Explicit credentials (access_key + secret_key parameters)
2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
3. IAM roles (automatic for AWS services)
4. AWS profile (~/.aws/credentials)

**Custom S3 Endpoints**:
```python
# MinIO
handler.handle(..., s3_endpoint="https://minio.example.com:9000")

# DigitalOcean Spaces
handler.handle(..., s3_endpoint="https://nyc3.digitaloceanspaces.com")

# Wasabi
handler.handle(..., s3_endpoint="https://s3.wasabisys.com")
```

## Common Features

All handlers share these features:

### File Filtering

Automatically skips:
- **Directories**: `.git`, `__pycache__`, `node_modules`, `.venv`, `venv`, `.env`, `dist`, `build`, `.cache`, `.pytest_cache`, `.mypy_cache`, `.tox`, `htmlcov`, `.coverage`, `.egg-info`
- **Extensions**: `.pyc`, `.pyo`, `.so`, `.dylib`, `.dll`, `.exe`, `.bin`, `.class`, `.o`, `.a`, `.obj`, `.lib`
- **Files**: `.DS_Store`, `Thumbs.db`, `.gitignore`, `.gitkeep`, `PKG-INFO`, `dependency_links.txt`, `top_level.txt`, `SOURCES.txt`, `requires.txt`

### .gitignore Support

RepoHandler, ArchiveHandler, and S3Handler respect `.gitignore` patterns if found in the source directory.

### Hash-Based Deduplication

- Computes SHA256 hash of file contents (streaming for memory efficiency)
- Stores hash in Qdrant payload as `parent_file_hash`
- Compares hashes to detect changes
- Only re-processes files when hash differs

### Parallel Processing

**RepoHandler._process_directory()** uses:
- **16 CPU workers** for file hashing (ProcessPoolExecutor)
- **4 thread workers** for chunking and uploading (ThreadPoolExecutor)
- **Batch operations**: 500 chunks accumulated, uploaded in batches of 100

### Progress Tracking

All handlers use `tqdm` for progress bars:
- File counting/downloading progress
- Processing progress
- Upload progress

## CLI Integration

All handlers are accessible via CLI:

```bash
# FileHandler
python -m app.cli upload file /path/to/file.pdf my_collection

# RepoHandler
python -m app.cli upload repo https://github.com/user/repo.git my_collection

# ArchiveHandler
python -m app.cli upload archive project.tar.gz my_collection

# S3Handler
python -m app.cli upload s3 my-bucket my_collection --prefix docs/
```

## Worker Integration

All handlers have corresponding worker functions for containerized execution:

```bash
# worker.py operations
python -m app.worker upload_file <file_path> <collection>
python -m app.worker upload_repo <repo_url> <collection>
python -m app.worker upload_archive <archive_path> <collection>
python -m app.worker upload_s3 <bucket> <collection> [--prefix <prefix>]
```

## Job System Integration

Each handler has a corresponding job class for distributed execution:

- `UploadFileJob` - Resources: 1 CPU, 2GB RAM, 30 min timeout
- `UploadRepoJob` - Resources: 2 CPU, 4GB RAM, 1 hour timeout
- `UploadS3Job` - Resources: 2 CPU, 4GB RAM, 1 hour timeout
- `CollectionJob` - Collection management operations

## Error Handling

All handlers implement comprehensive error handling:

### RepoHandler
- Git clone failures (SSH key not found, auth failed, etc.)
- Network errors during clone
- Invalid git URLs

### ArchiveHandler
- Unsupported archive format
- Corrupted archives
- Extraction failures

### S3Handler
- Bucket not found (`NoSuchBucket`)
- Access denied (`AccessDenied`)
- No credentials (`NoCredentialsError`)
- Network errors (`EndpointConnectionError`)
- Invalid S3 URI format

All errors are logged with context and raised with helpful messages.

## Extension Pattern

To add a new upload source (e.g., Google Drive):

1. **Create handler class** in `handlers.py`:
   ```python
   class DriveHandler:
       def __init__(self):
           self.repo_handler = RepoHandler()

       def handle(self, drive_folder_id, collection_name, ...):
           with tempfile.TemporaryDirectory() as temp_dir:
               # Download Drive contents to temp_dir
               self._download_drive_folder(drive_folder_id, temp_dir)

               # Delegate to existing processing
               self.repo_handler._process_directory(...)
   ```

2. **Create job class** in `jobs/upload_drive_job.py`

3. **Add CLI command** in `cli.py`

4. **Add worker function** in `worker.py`

This pattern maximizes code reuse by delegating to `RepoHandler._process_directory()`.
