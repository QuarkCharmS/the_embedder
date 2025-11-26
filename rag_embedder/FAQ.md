# RAG Embedder - Frequently Asked Questions (FAQ)

## Table of Contents
- [File Formats & Upload Methods](#file-formats--upload-methods)
- [Working with Your Own Files](#working-with-your-own-files)
- [Docker Usage](#docker-usage)
- [Collections](#collections)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)

---

## File Formats & Upload Methods

### What file types are supported?

The RAG Embedder uses `the_chunker` under the hood, which supports a wide variety of file formats:

**Programming Languages:**
- Python (`.py`)
- JavaScript/TypeScript (`.js`, `.ts`, `.jsx`, `.tsx`)
- Java (`.java`)
- C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)
- Go (`.go`)
- Rust (`.rs`)
- Ruby (`.rb`)
- PHP (`.php`)
- And many more...

**Documents:**
- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- PowerPoint (`.pptx`, `.ppt`)
- Excel (`.xlsx`, `.xls`)
- OpenDocument formats (`.odt`, `.ods`, `.odp`)
- Rich Text Format (`.rtf`)

**Text Formats:**
- Markdown (`.md`)
- Plain text (`.txt`)
- HTML (`.html`, `.htm`)
- XML (`.xml`)
- JSON (`.json`)
- YAML (`.yml`, `.yaml`)
- CSV (`.csv`)

**Archives:**
- ZIP (`.zip`)
- TAR (`.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`)
- Compressed archives (`.tgz`, `.tbz2`, `.txz`)

### Can I upload entire folders?

**Short answer:** Not directly, but you can zip them first.

**Long answer:** The system supports three upload methods:

1. **Individual files** - Upload one file at a time
2. **Archives** - Upload a `.zip` or `.tar.gz` containing multiple files
3. **Git repositories** - Upload entire codebases from GitHub/GitLab

To upload a folder:
```bash
# Zip your folder first
cd /path/to/your/folder
zip -r myproject.zip .

# Then upload the archive
docker run --rm \
  --network rag_network \
  -v $(pwd)/myproject.zip:/data/myproject.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/myproject.zip my-collection
```

### What files are automatically skipped?

When processing archives or repositories, these are automatically ignored:
- Build artifacts: `node_modules`, `dist`, `build`, `.cache`
- Python artifacts: `__pycache__`, `.pyc`, `.pyo`, `.venv`, `venv`
- Git directories: `.git`
- Binary files: `.exe`, `.dll`, `.so`, `.bin`, `.class`
- System files: `.DS_Store`, `Thumbs.db`
- Files matching `.gitignore` patterns (if present)

---

## Working with Your Own Files

### How do I upload my local codebase?

**Option 1: If it's a Git repository (recommended)**

If your code is in a Git repo (even if it's private):

```bash
# Push to GitHub/GitLab first
git push origin main

# Then upload directly (no mounting needed!)
docker run --rm \
  --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-hf-token" \
  -e QDRANT_HOST="qdrant" \
  -e GITHUB_TOKEN="your-github-token" \
  rag-embedder upload_repo https://github.com/username/repo my-collection
```

**Option 2: If it's not in Git**

Create an archive and upload it:

```bash
# Navigate to your project
cd /path/to/your/project

# Create a zip archive
zip -r myproject.zip . -x "*.git*" -x "*node_modules*" -x "*__pycache__*"

# Upload the archive
docker run --rm \
  --network rag_network \
  -v $(pwd)/myproject.zip:/data/myproject.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-hf-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/myproject.zip my-collection
```

### How do I upload my research papers/documentation?

**Single document:**
```bash
docker run --rm \
  --network rag_network \
  -v /path/to/paper.pdf:/data/paper.pdf \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_file /data/paper.pdf my-docs-collection
```

**Multiple documents:**
```bash
# Put all documents in a folder and zip it
cd /path/to/documents
zip -r documents.zip .

# Upload
docker run --rm \
  --network rag_network \
  -v $(pwd)/documents.zip:/data/documents.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/documents.zip my-docs-collection
```

### Can I mix different types of files in one collection?

**Yes!** You can upload code, documentation, PDFs, and other file types into the same collection. The chunker automatically detects file types and processes them appropriately.

Example workflow:
```bash
# Create collection
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_create my-project 384

# Upload codebase
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  -e GITHUB_TOKEN="your-github-token" \
  rag-embedder upload_repo https://github.com/username/repo my-project

# Upload documentation PDFs
docker run --rm --network rag_network \
  -v /path/to/docs.zip:/data/docs.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/docs.zip my-project
```

---

## Docker Usage

### Do I need to mount local files?

**It depends on what you're uploading:**

- **Git repositories:** ❌ No mounting needed - just provide the URL
- **Local files:** ✅ Yes, must mount them
- **Local archives:** ✅ Yes, must mount them

### How do I mount files from my host machine?

Use the `-v` flag to mount files or directories:

```bash
# Mount a single file
-v /host/path/file.txt:/container/path/file.txt

# Mount a directory
-v /host/path/folder:/container/folder

# Mount current directory
-v $(pwd)/file.txt:/data/file.txt
```

**Important:** The path after `:` is what the container sees. Use that path in your command.

Example:
```bash
docker run --rm \
  -v /home/user/myfile.pdf:/data/myfile.pdf \
  -e MODEL_NAME="..." -e API_TOKEN="..." -e QDRANT_HOST="qdrant" \
  rag-embedder upload_file /data/myfile.pdf my-collection
#                           ^^^^^^^^^^^^^^^^
#                           Use the container path!
```

### How do I connect to Qdrant running on my host?

**If Qdrant is in another Docker container:**
```bash
# Use the container name and network
docker run --rm \
  --network rag_network \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_list
```

**If Qdrant is running on your host machine:**
```bash
# Linux
docker run --rm -e QDRANT_HOST="172.17.0.1" rag-embedder collection_list

# Mac/Windows
docker run --rm -e QDRANT_HOST="host.docker.internal" rag-embedder collection_list
```

### Can I use Docker Compose?

**Yes!** Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant
    container_name: qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    networks:
      - rag_network

  embedder:
    image: rag-embedder
    environment:
      - MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
      - API_TOKEN=${API_TOKEN}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    volumes:
      - ./data:/data  # Mount local data folder
    depends_on:
      - qdrant
    networks:
      - rag_network

volumes:
  qdrant_storage:

networks:
  rag_network:
    driver: bridge
```

Then use it:
```bash
# Create collection
docker compose run --rm embedder collection_create my-collection 384

# Upload from mounted data folder
docker compose run --rm embedder upload_archive /data/myproject.zip my-collection

# Upload from GitHub
docker compose run --rm embedder upload_repo https://github.com/user/repo my-collection
```

---

## Collections

### What is a collection?

A **collection** is like a database table in Qdrant. Each collection stores embeddings for a set of documents. You can have multiple collections for different projects or use cases.

Examples:
- `python-stdlib` - Python standard library documentation
- `my-company-codebase` - Your company's internal codebase
- `research-papers` - Academic papers for a specific topic

### How do I create a collection?

```bash
docker run --rm \
  --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_create my-collection 384
```

**Important:** The dimension must match your embedding model:
- `sentence-transformers/all-MiniLM-L6-v2` → 384
- `sentence-transformers/all-mpnet-base-v2` → 768
- `text-embedding-ada-002` (OpenAI) → 1536
- `BAAI/bge-small-en-v1.5` → 384

### Can I update a collection with new files?

**Yes!** The system uses smart sync:

- **New files** → Added to collection
- **Modified files** → Old chunks deleted, new chunks added
- **Deleted files** → Chunks removed from collection
- **Unchanged files** → Skipped (no re-upload)

Just re-run the upload command with the same collection name:

```bash
# Initial upload
docker run --rm --network rag_network \
  -e MODEL_NAME="..." -e API_TOKEN="..." -e QDRANT_HOST="qdrant" \
  rag-embedder upload_repo https://github.com/user/repo my-collection

# Later, after code changes, run the same command again
docker run --rm --network rag_network \
  -e MODEL_NAME="..." -e API_TOKEN="..." -e QDRANT_HOST="qdrant" \
  rag-embedder upload_repo https://github.com/user/repo my-collection
# Only changed files will be processed!
```

### How do I list all collections?

```bash
docker run --rm \
  --network rag_network \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_list
```

### How do I delete a collection?

```bash
docker run --rm \
  --network rag_network \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_delete my-collection
```

---

## Common Use Cases

### Use Case 1: Index your company's codebase

```bash
# Step 1: Create collection
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_create company-codebase 384

# Step 2: Upload from private GitHub repo
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-hf-token" \
  -e QDRANT_HOST="qdrant" \
  -e GITHUB_TOKEN="ghp_yourtoken" \
  rag-embedder upload_repo https://github.com/company/repo company-codebase

# Step 3: Update daily (cron job)
0 0 * * * docker run --rm --network rag_network \
  -e MODEL_NAME="..." -e API_TOKEN="..." -e QDRANT_HOST="qdrant" \
  rag-embedder upload_repo https://github.com/company/repo company-codebase
```

### Use Case 2: Index multiple open-source projects

```bash
# Create collection
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_create python-ecosystem 384

# Upload multiple repos
for repo in "django/django" "pallets/flask" "psf/requests"; do
  docker run --rm --network rag_network \
    -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
    -e API_TOKEN="your-token" \
    -e QDRANT_HOST="qdrant" \
    rag-embedder upload_repo https://github.com/$repo python-ecosystem
done
```

### Use Case 3: Index local documentation

```bash
# Organize your docs
docs/
├── api-reference.pdf
├── user-guide.pdf
├── architecture.md
└── tutorials/
    ├── tutorial1.md
    └── tutorial2.md

# Zip them
cd docs
zip -r docs.zip .

# Upload
docker run --rm --network rag_network \
  -v $(pwd)/docs.zip:/data/docs.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/docs.zip company-docs
```

### Use Case 4: Work in progress local project

```bash
# While developing, periodically update your local codebase in the collection

# Zip your current work
cd /path/to/project
zip -r project.zip . -x "*.git*" -x "*node_modules*"

# Upload/update
docker run --rm --network rag_network \
  -v $(pwd)/project.zip:/data/project.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/project.zip my-wip-project
```

---

## Troubleshooting

### Error: "MODEL_NAME and API_TOKEN environment variables required"

You forgot to set the required environment variables. Make sure you include:
```bash
-e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"
-e API_TOKEN="your-huggingface-token"
```

**Getting an API token:**
- For HuggingFace models: Create a token at https://huggingface.co/settings/tokens
- For OpenAI models: Get your API key from https://platform.openai.com/api-keys

### Error: "Connection refused" or "Failed to connect to Qdrant"

**Problem:** Container can't reach Qdrant.

**Solutions:**

1. **Check if Qdrant is running:**
   ```bash
   docker ps | grep qdrant
   ```

2. **Verify network connection:**
   ```bash
   # Make sure both containers are on the same network
   docker network inspect rag_network
   ```

3. **Use correct QDRANT_HOST:**
   - Same Docker network: `QDRANT_HOST=qdrant` (container name)
   - Host machine Linux: `QDRANT_HOST=172.17.0.1`
   - Host machine Mac/Windows: `QDRANT_HOST=host.docker.internal`

### Error: "Archive not found" or "File not found"

**Problem:** The file isn't mounted correctly.

**Solution:** Check your mount path:
```bash
# Wrong - file doesn't exist in container
-v /host/file.zip /container/file.zip  # Missing the colon!

# Correct
-v /host/file.zip:/container/file.zip
```

Make sure the file path **after** the `:` is what you use in the command.

### The upload is very slow

**Causes:**
- Large embedding model (e.g., `all-mpnet-base-v2` is slower than `all-MiniLM-L6-v2`)
- Large files or many files
- Network latency to Qdrant

**Solutions:**
- Use a smaller/faster model for development
- Upload during off-peak hours
- Consider using GPU acceleration (not yet supported in Docker image)

### Files are being skipped that I want to include

**Check if they match skip patterns:**
- Hidden files starting with `.`
- Build artifacts (`node_modules`, `dist`, etc.)
- Files in `.gitignore` (if present)

**Solution:** Remove them from `.gitignore` or manually upload specific files using `upload_file`.

### How do I see what's happening during upload?

Set debug level in the code or check Docker logs:
```bash
# Run with docker logs
docker run --rm --network rag_network \
  -e MODEL_NAME="..." -e API_TOKEN="..." -e QDRANT_HOST="qdrant" \
  rag-embedder upload_repo https://github.com/user/repo my-collection 2>&1 | tee upload.log
```

### Can I upload extremely large codebases?

**Yes**, but be aware:
- Embedding generation takes time
- Large uploads may take hours
- Consider splitting into multiple collections

**Optimization tips:**
- Run overnight for large repos
- Use a faster embedding model
- Exclude unnecessary directories (tests, docs, vendor code)

---

## Getting Help

### Where can I find more examples?

- Check `DOCKER_WORKER_USAGE.md` for Docker-specific examples
- Check `ARCHITECTURE.md` for system design details
- Check `README.md` for general overview

### How do I report a bug?

Open an issue on the GitHub repository with:
- Description of the problem
- Command you ran
- Error message
- Docker logs

### Can I contribute?

Yes! Contributions are welcome. Check the repository for contribution guidelines.

---

## Quick Reference

### Essential Commands

```bash
# Build the image
docker build -f rag_embedder/Dockerfile -t rag-embedder .

# Create collection
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_create COLLECTION_NAME DIMENSION

# Upload GitHub repo
docker run --rm --network rag_network \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  -e GITHUB_TOKEN="your-github-token" \
  rag-embedder upload_repo REPO_URL COLLECTION_NAME

# Upload local file
docker run --rm --network rag_network \
  -v /host/path/file:/data/file \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_file /data/file COLLECTION_NAME

# Upload archive
docker run --rm --network rag_network \
  -v /host/path/archive.zip:/data/archive.zip \
  -e MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2" \
  -e API_TOKEN="your-token" \
  -e QDRANT_HOST="qdrant" \
  rag-embedder upload_archive /data/archive.zip COLLECTION_NAME

# List collections
docker run --rm --network rag_network \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_list

# Delete collection
docker run --rm --network rag_network \
  -e QDRANT_HOST="qdrant" \
  rag-embedder collection_delete COLLECTION_NAME
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MODEL_NAME` | Yes* | - | Embedding model (e.g., `sentence-transformers/all-MiniLM-L6-v2`) |
| `API_TOKEN` | Yes* | - | HuggingFace or OpenAI API token |
| `QDRANT_HOST` | No | `localhost` | Qdrant server hostname |
| `QDRANT_PORT` | No | `6333` | Qdrant server port |
| `GITHUB_TOKEN` | No | - | GitHub personal access token for private repos |

\* Required for upload operations, not for collection management

### Common Model Dimensions

| Model | Dimension |
|-------|-----------|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `sentence-transformers/all-mpnet-base-v2` | 768 |
| `BAAI/bge-small-en-v1.5` | 384 |
| `BAAI/bge-base-en-v1.5` | 768 |
| `BAAI/bge-large-en-v1.5` | 1024 |
| `text-embedding-ada-002` (OpenAI) | 1536 |
