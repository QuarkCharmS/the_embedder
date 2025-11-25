# RAG in AWS - System Architecture

## Overview

This is a Retrieval-Augmented Generation (RAG) system that processes files, generates embeddings, and stores them in Qdrant vector database. The system can run locally, in Docker, Kubernetes, or AWS Batch.

## Core Components

### 1. Entry Points

**app/cli.py** - Main CLI interface using Click
- Provides commands: `upload`, `collection`, `sync`
- Validates arguments and spawns jobs
- Entry point: `python -m app.cli <command>`

**app/__main__.py** - Module entry point
- Allows `python -m app` to work
- Simply imports and calls `cli.main()`

**app/worker.py** - Container worker entry point
- Lightweight CLI for containerized execution
- Parses sys.argv directly (no Click dependency)
- Entry point for Docker/K8s: `python -m app.worker <operation> <args>`

### 2. Job System (jobs/)

**jobs/base.py** - Abstract base class for all jobs
- Defines job interface: `build_command()`, `get_env_vars()`
- Validates parameters
- Template pattern for job execution

**Concrete Job Classes**:
- **jobs/upload_file_job.py** - Upload single file
- **jobs/upload_repo_job.py** - Clone and upload git repository
- **jobs/collection_job.py** - Collection operations (create/delete/list)

Jobs are **stateless** - they just build commands and environment variables for runtimes to execute.

### 3. Runtime System (runtimes/)

**runtimes/factory.py** - Runtime selection logic
- Chooses runtime based on `runtime` parameter
- Maps: "local" → LocalRuntime, "docker" → DockerRuntime, etc.

**Runtime Implementations**:
- **runtimes/local.py** - Direct subprocess execution
- **runtimes/docker.py** - Docker container execution
- **runtimes/kubernetes.py** - K8s Job execution
- **runtimes/aws_batch.py** - AWS Batch job submission

All runtimes implement `execute(command, env_vars)` and return success/failure.

### 4. Handlers (app/handlers.py)

**Purpose**: Execute the actual upload logic (called by worker.py)

**Three Handler Classes**:

1. **FileHandler** - Upload single file
   - Validates file exists
   - Gets file hash
   - Calls QdrantManager.upload_file()

2. **RepoHandler** - Clone and upload git repository
   - Clones repo using smart_git_clone()
   - Analyzes project structure
   - Processes directory with QdrantManager

3. **ArchiveHandler** - Extract and upload archive
   - Extracts to temp directory
   - Processes directory
   - Cleans up temp files

### 5. Qdrant Integration

**app/qdrant_manager.py** - Main orchestrator for Qdrant operations

**Key Operations**:
- `create_collection()` - Create Qdrant collection with metadata
- `delete_collection()` - Delete collection
- `list_collections()` - List all collections
- `upload_file()` - Chunk single file and upload to Qdrant
- `upload_directory()` - Process entire directory tree
- `sync_directory()` - Smart sync with hash-based change detection

**Sync Logic** (most complex):
1. Get existing files from Qdrant metadata
2. Calculate hashes for current files
3. Determine operations: add, update, delete
4. Execute deletions (remove points from Qdrant)
5. Execute updates (re-chunk and replace)
6. Execute additions (chunk and upload new files)

**app/qdrant_chunker.py** - Chunking logic
- Splits files into chunks based on extension
- Markdown: by headers, Python: by classes/functions, generic: by lines
- Each chunk gets metadata: file_path, chunk_index, hash

**app/qdrant_uploader.py** - Batch upload to Qdrant
- Parallel embedding generation using ThreadPoolExecutor
- Batch upsert to Qdrant (100 points at a time)
- Progress tracking

### 6. Embedding Generation

**app/embedder.py** - API client for embedding service
- Calls external embedding API (configurable model)
- Supports batch embedding (multiple texts at once)
- Returns numpy arrays

### 7. Utilities

**app/git_utils.py** - Smart git cloning
- Auto-detects SSH vs HTTPS URLs
- SSH: searches for keys in ~/.ssh/, tries each one
- HTTPS: tries without auth first, then with token
- Provides helpful error messages

**app/project_analyzer.py** - Python project analysis
- Parses Python files with AST
- Extracts imports, classes, functions
- Generates dependency graph
- Creates summary document

**app/config.py** - Shared constants
- File size limits, chunk sizes, supported extensions
- Color definitions for output
- Timeout values

**app/logger.py** - Centralized logging
- Creates logger with consistent format
- Configurable log level
- Color-coded output

## Execution Flow

### Flow 1: Upload File (Local Runtime)

```
User runs: python -m app upload file /path/to/file.py my_collection

1. cli.py:upload_file() called
   - Validates arguments
   - Creates UploadFileJob
   - Creates LocalRuntime
   - Calls runtime.execute()

2. LocalRuntime.execute()
   - Builds command: ["python", "-m", "app.worker", "upload_file", "/path/to/file.py", "my_collection"]
   - Sets env vars: MODEL_NAME, API_TOKEN, QDRANT_HOST, etc.
   - Runs subprocess

3. worker.py:upload_file() called
   - Gets config from environment
   - Creates FileHandler
   - Calls handler.handle()

4. FileHandler.handle()
   - Validates file exists
   - Calculates file hash
   - Creates QdrantManager
   - Calls manager.upload_file()

5. QdrantManager.upload_file()
   - Creates QdrantChunker
   - Calls chunker.chunk_file()
   - Gets list of chunks

6. QdrantChunker.chunk_file()
   - Detects file type
   - Chunks based on type (Python: by function, Markdown: by header)
   - Returns chunks with metadata

7. QdrantManager.upload_file() continues
   - Creates QdrantUploader
   - Calls uploader.upload_chunks()

8. QdrantUploader.upload_chunks()
   - Creates Embedder
   - Parallel: generates embeddings for all chunks
   - Batch upserts to Qdrant (100 at a time)
   - Returns success

9. Exit with code 0
```

### Flow 2: Upload Repo (Docker Runtime)

```
User runs: python -m app upload repo https://github.com/user/repo.git my_collection --runtime docker

1. cli.py:upload_repo() called
   - Validates URL
   - Creates UploadRepoJob
   - Creates DockerRuntime
   - Calls runtime.execute()

2. DockerRuntime.execute()
   - Builds docker run command
   - Mounts volumes if needed (for SSH keys)
   - Passes env vars with -e flags
   - Command: ["upload_repo", "https://github.com/user/repo.git", "my_collection"]
   - Runs docker

3. Container starts, worker.py:upload_repo() called
   - Gets config from environment
   - Creates RepoHandler
   - Calls handler.handle()

4. RepoHandler.handle()
   - Creates temp directory
   - Calls smart_git_clone()

5. smart_git_clone() (git_utils.py)
   - Detects HTTPS URL
   - Tries clone without auth
   - If fails and token provided, injects token
   - Clones to temp directory

6. RepoHandler.handle() continues
   - Calls ProjectAnalyzer.analyze_python_dependencies()
   - Saves analysis to .rag_metadata/analysis.txt

7. ProjectAnalyzer.analyze_python_dependencies()
   - Walks directory tree
   - Parses Python files with AST
   - Extracts imports, classes, functions
   - Generates dependency graph
   - Returns formatted analysis text

8. RepoHandler.handle() continues
   - Creates QdrantManager
   - Calls manager.upload_directory()

9. QdrantManager.upload_directory()
   - Walks directory tree
   - Filters by supported extensions
   - For each file: upload_file()
   - Progress bar with tqdm

10. (Same as steps 5-8 from Flow 1 for each file)

11. Cleans up temp directory
12. Container exits with code 0
```

### Flow 3: Sync Directory (Local)

```
User runs: python -m app sync /path/to/repo my_collection

1. cli.py:sync_directory() called
   - Validates directory exists
   - Creates QdrantManager directly (no job/runtime)
   - Calls manager.sync_directory()

2. QdrantManager.sync_directory()
   - Gets collection info
   - Extracts existing_files from metadata

3. _scroll_all_files_metadata() helper
   - Scrolls through all points in collection
   - Extracts file_path and hash from each point
   - Returns dict: {file_path: hash}

4. _scan_current_files() helper
   - Walks directory tree
   - Filters by supported extensions
   - Calculates hash for each file
   - Returns dict: {file_path: hash}

5. _determine_sync_operations()
   - Compares existing_files vs current_files
   - to_delete: files in Qdrant but not on disk
   - to_update: files with different hashes
   - to_add: files on disk but not in Qdrant
   - Returns (to_delete, to_update, to_add)

6. _execute_deletions()
   - For each file in to_delete:
     - Delete all points with that file_path from Qdrant
     - Uses Filter + FieldCondition

7. _execute_updates()
   - For each file in to_update:
     - Delete old points
     - Call upload_file() to re-chunk and upload

8. _execute_additions()
   - For each file in to_add:
     - Call upload_file() to chunk and upload

9. Print sync summary
10. Exit with code 0
```

## Data Flow

### Embedding Storage in Qdrant

Each chunk is stored as a **point** in Qdrant with:

**Vector**: Embedding array (e.g., 4096 dimensions for Qwen3-Embedding-8B)

**Payload**:
```json
{
  "file_path": "src/handlers.py",
  "content": "class FileHandler:\n    def handle(...)...",
  "chunk_index": 0,
  "file_hash": "abc123def456",
  "timestamp": "2025-11-24T10:30:00"
}
```

**Collection Metadata**:
```json
{
  "model": "Qwen/Qwen3-Embedding-8B",
  "dimension": 4096,
  "created_at": "2025-11-24T10:00:00"
}
```

### File Hash Calculation

Used for change detection in sync operations:

```python
def calculate_hash(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()
```

Stored in each chunk's payload so sync can compare hashes.

## Communication Between Modules

### CLI → Job → Runtime → Worker → Handler → QdrantManager

1. **CLI** validates user input, creates Job object
2. **Job** builds command and environment variables
3. **Runtime** executes command in appropriate environment
4. **Worker** receives command, parses args, calls Handler
5. **Handler** orchestrates operation, calls QdrantManager
6. **QdrantManager** coordinates chunking, embedding, upload

### Parallel Processing

**Embedding Generation** (qdrant_uploader.py):
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(embedder.embed, chunk) for chunk in chunks]
    embeddings = [f.result() for f in futures]
```

**Directory Upload** (qdrant_manager.py):
- Sequential file processing (for progress tracking)
- Could be parallelized but prioritizes user feedback

## Configuration

### Environment Variables

Required for all upload operations:
- `MODEL_NAME` - Embedding model (e.g., "Qwen/Qwen3-Embedding-8B")
- `API_TOKEN` - API token for embedding service
- `QDRANT_HOST` - Qdrant server host (default: "localhost")
- `QDRANT_PORT` - Qdrant server port (default: "6333")

Optional:
- `GITHUB_TOKEN` - For private git repositories

### Runtime-Specific Config

**Docker**:
- Image name from config (default: "rag-worker:latest")
- Volume mounts for SSH keys if needed
- Network configuration for Qdrant access

**Kubernetes**:
- Namespace, service account
- Resource limits (CPU, memory)
- Image pull secrets

**AWS Batch**:
- Job queue, job definition
- IAM roles
- VPC configuration

## Error Handling

### Git Clone Errors (git_utils.py)

- **SSH without keys**: "No SSH keys found. Mount key or run ssh-keygen..."
- **SSH auth failed**: "All keys failed. Ensure public key added to provider..."
- **HTTPS private repo**: "Repository private but no token. Generate PAT at..."
- **HTTPS token failed**: "Token invalid. Check expiration and repo scope..."

### Qdrant Errors (qdrant_manager.py)

- **Collection exists**: "Collection already exists. Use sync or delete first."
- **Collection not found**: "Collection not found. Create it first."
- **Connection error**: "Cannot connect to Qdrant at host:port"

### File Processing Errors (handlers.py)

- **File not found**: "File does not exist: {path}"
- **Unsupported file type**: "File type not supported: {extension}"
- **File too large**: "File exceeds size limit: {size} > {MAX_SIZE}"

All errors are logged with context and raised with helpful messages.

## Key Design Decisions

### 1. Stateless Jobs
Jobs only build commands/env vars. They don't execute logic. This allows:
- Easy serialization for async execution
- Runtime can be changed without modifying job
- Testing is straightforward

### 2. Worker as Thin Wrapper
worker.py is minimal - just arg parsing and handler delegation. This:
- Keeps container images small
- Makes debugging easier
- Separates concerns (parsing vs execution)

### 3. Hash-Based Sync
Instead of timestamps, we use file content hashes. This:
- Avoids clock sync issues across systems
- Detects actual content changes
- Works reliably in containers

### 4. Metadata in Chunks
Each chunk stores file_path, hash, timestamp. This:
- Enables smart sync without external database
- Allows point-in-time recovery
- Makes debugging easier

### 5. Parallel Embedding, Sequential Upload
Embeddings generated in parallel (CPU-bound), but Qdrant uploads sequential. This:
- Maximizes embedding throughput
- Avoids overwhelming Qdrant
- Provides clear progress feedback

## Extension Points

### Adding New File Types

1. Add extension to `SUPPORTED_EXTENSIONS` in config.py
2. Add chunking logic in qdrant_chunker.py `chunk_file()`
3. No other changes needed

### Adding New Runtimes

1. Create new class in runtimes/ extending BaseRuntime
2. Implement `execute(command, env_vars)`
3. Register in RuntimeFactory
4. No changes to jobs or handlers

### Adding New Upload Sources

1. Create new Handler in handlers.py
2. Create new Job in jobs/
3. Add CLI command in cli.py
4. Add worker function in worker.py

## Deployment Patterns

### Local Development
```bash
python -m app upload file document.pdf my_docs
python -m app sync ./my_project my_docs
```

### Docker
```bash
docker run -e MODEL_NAME=... -e API_TOKEN=... \
  rag-worker:latest upload_repo https://github.com/user/repo my_docs
```

### Kubernetes Job
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: upload-repo
spec:
  template:
    spec:
      containers:
      - name: worker
        image: rag-worker:latest
        args: ["upload_repo", "https://github.com/user/repo", "my_docs"]
        env:
        - name: MODEL_NAME
          value: "Qwen/Qwen3-Embedding-8B"
        - name: API_TOKEN
          valueFrom:
            secretKeyRef:
              name: api-token
              key: token
      restartPolicy: Never
```

### AWS Batch
Submitted via AWS SDK with:
- Job definition: container image, resources
- Job queue: execution environment
- Parameters: command, env vars
- Dependencies: other jobs in workflow

## Performance Characteristics

### Bottlenecks

1. **Embedding Generation** - API calls are slowest
   - Mitigated by parallel requests (5 workers)
   - Batch embedding when API supports it

2. **File I/O** - Reading large repos
   - Mitigated by processing incrementally
   - Sync operations only process changed files

3. **Network** - Qdrant upload bandwidth
   - Mitigated by batch upserts (100 points/batch)
   - Could use Qdrant's gRPC API for better performance

### Scaling Strategies

- **Horizontal**: Run multiple workers in parallel on different repos
- **Vertical**: Increase ThreadPoolExecutor workers for embedding
- **Sharding**: Split large repos into multiple collections
- **Caching**: Cache embeddings for unchanged files (future enhancement)

## Security Considerations

### Secrets Management

- API tokens passed via environment variables (not in code/logs)
- SSH keys mounted read-only in containers
- Git tokens injected into URLs temporarily (not persisted)

### Input Validation

- File paths validated before processing
- Git URLs parsed and validated
- File sizes checked against limits
- File types restricted by allowlist

### Network Security

- Qdrant connection can use TLS
- Embedding API supports token authentication
- Container networks isolated in K8s

## Testing Strategy

Each module has clear boundaries, making testing straightforward:

- **Jobs**: Test command/env var generation (no execution)
- **Runtimes**: Mock subprocess/docker/k8s clients
- **Handlers**: Mock QdrantManager, test orchestration
- **QdrantManager**: Mock Qdrant client, test logic
- **Chunker**: Test chunk generation with sample files
- **Embedder**: Mock API client, test batch processing

Integration tests can use test Qdrant instance and mock embedding API.
