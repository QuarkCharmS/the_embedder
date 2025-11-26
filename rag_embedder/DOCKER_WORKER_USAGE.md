# Docker Worker Usage Guide

This guide explains how to build and use the 2-stage RAG Embedder Docker image for containerized operations.

## Building the Image

The Dockerfile must be built from the **parent directory** (one level up from rag_embedder) since it needs access to both `the_chunker` and `rag_embedder` directories:

```bash
cd /home/santiago/rag_in_aws_the_big_project
docker build -f rag_embedder/Dockerfile -t rag-embedder .
```

### Build Stages

**Stage 1 (Builder):**
- Installs `the_chunker` package and its dependencies
- Installs `rag_embedder` requirements
- All dependencies are installed into Python site-packages

**Stage 2 (Runtime):**
- Copies only the installed packages from Stage 1
- Copies the `app/` codebase
- Sets up `worker.py` as the entrypoint
- Lightweight final image

## Running Operations

The container accepts commands through `worker.py` as the entrypoint. All environment variables are passed at runtime.

### Required Environment Variables

- `MODEL_NAME` - The embedding model to use
- `API_TOKEN` - API token for the embedding service
- `QDRANT_HOST` - Qdrant host (default: localhost)
- `QDRANT_PORT` - Qdrant port (default: 6333)

### Optional Environment Variables

- `GITHUB_TOKEN` - GitHub token for private repositories (can also use `--git-token` flag)

## Available Commands

### 1. Upload Repository

```bash
docker run --rm \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="localhost" \
  -e QDRANT_PORT="6333" \
  -e GITHUB_TOKEN="your-github-token" \
  rag-embedder upload_repo https://github.com/user/repo my-collection
```

With inline git token:
```bash
docker run --rm \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="localhost" \
  rag-embedder upload_repo https://github.com/user/repo my-collection --git-token your-token
```

### 2. Upload File

```bash
docker run --rm \
  -v /path/to/local/file.txt:/data/file.txt \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="localhost" \
  rag-embedder upload_file /data/file.txt my-collection
```

### 3. Upload Archive

```bash
docker run --rm \
  -v /path/to/archive.zip:/data/archive.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="localhost" \
  rag-embedder upload_archive /data/archive.zip my-collection
```

### 4. Create Collection

```bash
docker run --rm \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="localhost" \
  rag-embedder collection_create my-collection 384
```

### 5. Delete Collection

```bash
docker run --rm \
  -e QDRANT_HOST="localhost" \
  rag-embedder collection_delete my-collection
```

### 6. List Collections

```bash
docker run --rm \
  -e QDRANT_HOST="localhost" \
  rag-embedder collection_list
```

## Using with Docker Compose

Create a `.env` file with your configuration:

```env
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
API_TOKEN=your-api-token
QDRANT_HOST=qdrant
QDRANT_PORT=6333
GITHUB_TOKEN=your-github-token
```

Then run operations:

```bash
docker compose run --rm embedder upload_repo https://github.com/user/repo my-collection
```

## Network Configuration

To connect to a Qdrant instance running in another container:

```bash
docker run --rm \
  --network your-docker-network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="qdrant-container-name" \
  rag-embedder collection_list
```

## Mounting Volumes for File Operations

When uploading files or archives, mount the directory containing your files:

```bash
docker run --rm \
  -v $(pwd)/data:/data \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-api-token" \
  -e QDRANT_HOST="localhost" \
  rag-embedder upload_file /data/mydocument.pdf my-collection
```

## Help

To see available commands:

```bash
docker run --rm rag-embedder
```

## Architecture

- **Entrypoint:** `python -m app.worker`
- **Working Directory:** `/app`
- **Python Path:** `/app`
- **Installed Packages:** All dependencies are in `/usr/local/lib/python3.12/site-packages`

## Troubleshooting

### Connection Errors

If you can't connect to Qdrant:
- Ensure `QDRANT_HOST` is correctly set
- If Qdrant is running on the host, use `host.docker.internal` (Mac/Windows) or `172.17.0.1` (Linux)
- If Qdrant is in another container, ensure both containers are on the same network

### Missing Dependencies

If you get import errors:
- Rebuild the image: `docker build -f rag_embedder/Dockerfile -t rag-embedder .`
- Check that both stages completed successfully

### Environment Variables

If operations fail with missing configuration:
- Verify all required environment variables are set
- Check that `MODEL_NAME` and `API_TOKEN` are provided for upload operations
