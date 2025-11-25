# Docker Usage Guide - RAG CLI

Complete guide for running the RAG CLI Docker container with environment variables, SSH keys, and various upload scenarios.

---

## Building the Image

**Always build from the parent directory:**

```bash
cd /home/santiago/rag_in_aws_the_big_project
docker build -f rag_embedder/Dockerfile -t rag-cli:latest .
```

Tag for registry:
```bash
docker build -f rag_embedder/Dockerfile -t your-registry/rag-cli:v1.0.0 .
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `QDRANT_HOST` | Qdrant server hostname | `qdrant`, `localhost`, `qdrant.example.com` |
| `MODEL_NAME` | Embedding model name | `text-embedding-3-large`, `Qwen/Qwen3-Embedding-8B` |
| `API_TOKEN` | API token for embedding provider | Your API token |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_PORT` | Qdrant server port | `6333` |
| `GITHUB_TOKEN` | GitHub personal access token for private repos | None |
| `DEBUG` | Enable debug output (`NONE`, `PARTIAL`, `FULL`) | `NONE` |

---

## Basic Usage Examples

### 1. Upload a Public Git Repository

```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git my_collection
```

### 2. Upload a File from Host Machine

Mount a local directory to `/data` in the container:

```bash
docker run --rm \
  --network host \
  -v /path/to/your/files:/data:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  rag-cli:latest \
  upload file /data/document.pdf my_collection
```

**Example with actual path:**
```bash
docker run --rm \
  --network host \
  -v /home/santiago/Documents:/data:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=sk-1234567890abcdef \
  rag-cli:latest \
  upload file /data/report.pdf documents
```

### 3. Upload an Archive (ZIP/TAR)

```bash
docker run --rm \
  --network host \
  -v /path/to/archives:/data:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  rag-cli:latest \
  upload archive /data/documents.zip my_collection
```

### 4. Upload a Local Git Repository Archive

If you have a `.zip` file containing a repo (with `.git` directory):

```bash
docker run --rm \
  --network host \
  -v /path/to/repos:/data:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  rag-cli:latest \
  upload repo /data/my-repo.zip my_collection
```

---

## Working with Private Repositories

### Method 1: SSH Keys (Recommended)

Mount your SSH keys as read-only:

```bash
docker run --rm \
  --network host \
  -v ~/.ssh:/root/.ssh:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  rag-cli:latest \
  upload repo git@github.com:user/private-repo.git my_collection
```

**Important SSH Notes:**
- Mount as `:ro` (read-only) for security
- Ensure your SSH keys have proper permissions on host: `chmod 600 ~/.ssh/id_rsa`
- Your `~/.ssh/config` file will be respected
- Known hosts file will be used from mounted directory

**Testing SSH access before running:**
```bash
# Test that your SSH key works
ssh -T git@github.com

# Then run with Docker
docker run --rm \
  --network host \
  -v ~/.ssh:/root/.ssh:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  rag-cli:latest \
  upload repo git@github.com:myorg/private-repo.git collection_name
```

### Method 2: HTTPS with GitHub Token

Use a GitHub Personal Access Token:

```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token-here \
  -e GITHUB_TOKEN=ghp_yourGitHubTokenHere \
  rag-cli:latest \
  --git-token $GITHUB_TOKEN \
  upload repo https://github.com/user/private-repo.git my_collection
```

**Creating a GitHub Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Use the token in the command above

---

## Using Docker Compose

### Interactive Development

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    networks:
      - rag-network

  rag-cli:
    build:
      context: ..
      dockerfile: rag_embedder/Dockerfile
    environment:
      - QDRANT_HOST=qdrant
      - MODEL_NAME=${MODEL_NAME}
      - API_TOKEN=${API_TOKEN}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    networks:
      - rag-network
    volumes:
      - ./data:/data
      - ~/.ssh:/root/.ssh:ro
    depends_on:
      qdrant:
        condition: service_healthy
    # Keep container running for interactive use
    command: tail -f /dev/null

volumes:
  qdrant_storage:

networks:
  rag-network:
```

Create `.env` file:
```bash
MODEL_NAME=text-embedding-3-large
API_TOKEN=your-api-token
GITHUB_TOKEN=ghp_yourtoken
```

Run and execute commands:
```bash
# Start services
docker-compose up -d

# Execute commands inside container
docker-compose exec rag-cli python -m app.cli --help

docker-compose exec rag-cli python -m app.cli \
  --model text-embedding-3-large \
  --api-token $API_TOKEN \
  upload repo https://github.com/user/repo.git my_collection

# Stop services
docker-compose down
```

### One-Shot Jobs

Use the provided `docker-compose.job.yml`:

```bash
# Set environment variables
export MODEL_NAME=text-embedding-3-large
export API_TOKEN=your-api-token
export GITHUB_TOKEN=ghp_yourtoken

# Run specific job
docker-compose -f docker-compose.job.yml up upload-repo-job

# View logs
docker-compose -f docker-compose.job.yml logs -f upload-repo-job
```

**Customize the job** by editing `docker-compose.job.yml`:
```yaml
upload-repo-job:
  # ... other config ...
  command: >
    --model ${MODEL_NAME}
    --api-token ${API_TOKEN}
    upload repo https://github.com/your/repo.git your_collection
```

---

## Network Configuration

### Using Host Network (Simplest)

```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  # ... other options
```

This allows the container to access services on `localhost` directly.

### Using Bridge Network with Qdrant Container

```bash
# Create network
docker network create rag-network

# Run Qdrant
docker run -d \
  --name qdrant \
  --network rag-network \
  -p 6333:6333 \
  qdrant/qdrant:latest

# Run RAG CLI (note QDRANT_HOST=qdrant, the container name)
docker run --rm \
  --network rag-network \
  -e QDRANT_HOST=qdrant \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git my_collection
```

### Using External Qdrant Instance

```bash
docker run --rm \
  -e QDRANT_HOST=qdrant.mycompany.com \
  -e QDRANT_PORT=6333 \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git my_collection
```

---

## Advanced Examples

### Multiple Files from Directory

Upload all PDFs from a directory:

```bash
docker run --rm \
  --network host \
  -v /home/user/documents:/data:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  rag-cli:latest \
  upload archive /data/all-documents.zip documents_collection
```

### Using Different Embedding Models

**OpenAI:**
```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=sk-your-openai-key \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git collection
```

**Voyage AI:**
```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=voyage-large-2-instruct \
  -e API_TOKEN=pa-your-voyage-key \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git collection
```

**DeepInfra (HuggingFace models):**
```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=Qwen/Qwen3-Embedding-8B \
  -e API_TOKEN=your-deepinfra-key \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git collection
```

### Enable Debug Output

```bash
docker run --rm \
  --network host \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  -e DEBUG=FULL \
  rag-cli:latest \
  upload repo https://github.com/user/repo.git my_collection
```

Debug levels:
- `NONE` - No debug output (default)
- `PARTIAL` - Show file processing
- `FULL` - Show detailed chunking information

### With Custom SSH Config

If you have a custom SSH config:

```bash
docker run --rm \
  --network host \
  -v ~/.ssh:/root/.ssh:ro \
  -e QDRANT_HOST=localhost \
  -e MODEL_NAME=text-embedding-3-large \
  -e API_TOKEN=your-api-token \
  rag-cli:latest \
  upload repo git@custom-host:user/repo.git collection
```

Your `~/.ssh/config` will be used:
```
Host custom-host
    HostName git.company.com
    User git
    IdentityFile ~/.ssh/company_rsa
```

---

## Complete Real-World Example

Here's a complete example with all the pieces together:

```bash
#!/bin/bash
set -e

# Configuration
REGISTRY="ghcr.io/mycompany"
IMAGE_TAG="v1.0.0"
QDRANT_HOST="qdrant.production.company.com"
MODEL_NAME="text-embedding-3-large"
API_TOKEN="sk-proj-..."  # Store in secure vault in production
COLLECTION_NAME="company_docs"
REPO_URL="git@github.com:company/docs.git"

# Build image
cd /home/santiago/rag_in_aws_the_big_project
docker build -f rag_embedder/Dockerfile -t ${REGISTRY}/rag-cli:${IMAGE_TAG} .

# Push to registry (if needed)
docker push ${REGISTRY}/rag-cli:${IMAGE_TAG}

# Run upload job
docker run --rm \
  --name rag-upload-job \
  -v ~/.ssh:/root/.ssh:ro \
  -e QDRANT_HOST=${QDRANT_HOST} \
  -e QDRANT_PORT=6333 \
  -e MODEL_NAME=${MODEL_NAME} \
  -e API_TOKEN=${API_TOKEN} \
  -e DEBUG=PARTIAL \
  ${REGISTRY}/rag-cli:${IMAGE_TAG} \
  upload repo ${REPO_URL} ${COLLECTION_NAME}

echo "Upload completed successfully!"
```

---

## Troubleshooting

### Cannot connect to Qdrant

**Error:** `Failed to connect to Qdrant at localhost:6333`

**Solutions:**
1. Use `--network host` if Qdrant is on localhost
2. Use Docker network if Qdrant is in a container
3. Check `QDRANT_HOST` points to correct hostname/IP
4. Verify Qdrant is running: `curl http://localhost:6333/health`

### SSH Key Permission Denied

**Error:** `Permission denied (publickey)`

**Solutions:**
1. Verify SSH key works on host: `ssh -T git@github.com`
2. Check key permissions: `chmod 600 ~/.ssh/id_rsa`
3. Ensure mounting correct SSH directory: `-v ~/.ssh:/root/.ssh:ro`
4. Add SSH key to ssh-agent on host first

### GitHub Token Authentication Fails

**Error:** `Authentication failed`

**Solutions:**
1. Verify token has `repo` scope
2. Pass token via both environment and CLI flag:
   ```bash
   -e GITHUB_TOKEN=ghp_token \
   rag-cli:latest \
   --git-token $GITHUB_TOKEN \
   upload repo ...
   ```
3. Check token hasn't expired

### Volume Mount Issues

**Error:** `No such file or directory` when accessing `/data`

**Solutions:**
1. Use absolute paths: `-v /home/user/files:/data:ro`
2. Verify host directory exists
3. Check file permissions on host

### Out of Memory

**Error:** Container killed or `MemoryError`

**Solutions:**
1. Increase Docker memory limit:
   ```bash
   docker run --rm \
     --memory=4g \
     --memory-swap=4g \
     # ... other options
   ```
2. Process smaller repositories
3. Upload files individually instead of large archives

---

## Security Best Practices

1. **Never hardcode secrets** - Use environment variables or Docker secrets
2. **Mount SSH keys as read-only** - Always use `:ro` flag
3. **Use minimal permissions** - Don't run as root in production (add USER directive to Dockerfile)
4. **Scan images** - Run `docker scan rag-cli:latest` before deploying
5. **Use specific image tags** - Don't use `:latest` in production
6. **Store tokens securely** - Use secret management (HashiCorp Vault, AWS Secrets Manager, etc.)
7. **Limit network access** - Only expose necessary ports
8. **Regular updates** - Rebuild images with updated base images and dependencies

---

## Quick Reference

### Minimal Command Structure

```bash
docker run --rm \
  -e QDRANT_HOST=<host> \
  -e MODEL_NAME=<model> \
  -e API_TOKEN=<token> \
  rag-cli:latest \
  upload <type> <source> <collection>
```

### Upload Types

- `upload repo <git-url> <collection>` - Git repository
- `upload repo <path.zip> <collection>` - Local repo archive (with .git)
- `upload file <path> <collection>` - Single file
- `upload archive <path> <collection>` - Archive (zip/tar)

### Common Options

- `--model <name>` - Override MODEL_NAME env var
- `--api-token <token>` - Override API_TOKEN env var
- `--qdrant-host <host>` - Override QDRANT_HOST env var
- `--qdrant-port <port>` - Override QDRANT_PORT env var
- `--git-token <token>` - GitHub token for private repos
- `--help` - Show help message

---

## Next Steps

- See [DEPLOYMENT.md](./DEPLOYMENT.md) for Kubernetes deployment
- See [README.md](./README.md) for CLI usage and features
- Check `docker-compose.job.yml` for batch job examples
- Review `kubernetes-job-example.yaml` for production deployments
