# RAG in AWS

A powerful CLI tool for ingesting documents, code repositories, and archives into Qdrant vector database with automatic semantic chunking and embedding generation. Perfect for building RAG (Retrieval-Augmented Generation) systems.

## Features

- **Multiple Source Types**: Upload files, git repositories, or archives (.zip, .tar.gz, etc.)
- **Smart Chunking**: Automatic semantic chunking with support for 20+ file formats
- **Flexible Embeddings**: Works with any embedding provider (OpenAI, DeepInfra, Cohere, Voyage AI, etc.)
- **Incremental Sync**: Hash-based change detection for efficient updates
- **Git Support**: Clone public/private repos with SSH key auto-detection
- **Docker Ready**: Full Docker support
- **Parallel Processing**: Optimized for speed with concurrent file processing

## Supported File Types

- **Documents**: PDF, DOCX, ODT, RTF, TXT, MD
- **Spreadsheets**: XLSX, XLS, ODS, CSV
- **Presentations**: PPTX, PPT, ODP
- **Code**: Python, JavaScript, TypeScript, Java, C++, Go, Rust, and more
- **Web**: HTML, XML, JSON, YAML
- **Archives**: ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ

## Quick Start

### 1. Installation

#### Option A: Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/rag_in_aws.git
cd rag_in_aws

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API tokens
```

#### Option B: Docker Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/rag_in_aws.git
cd rag_in_aws

# Set up environment variables
cp .env.example .env
# Edit .env with your API tokens

# Start Qdrant and build the CLI
docker-compose up -d
```

### 2. Configure Environment Variables

Edit `.env` file with your credentials:

```bash
# Required
MODEL_NAME=Qwen/Qwen3-Embedding-8B
API_TOKEN=your_api_token_here  # Works with any provider (DeepInfra, OpenAI, etc.)

# Optional
QDRANT_HOST=localhost
QDRANT_PORT=6333
GITHUB_TOKEN=your_github_token  # For private repos
```

### 3. Create a Collection and Upload

```bash
# Step 1: Create a collection with your embedding model
python -m app.cli collections create my_collection \
  --vector-size 4096 \
  --embedding-model "Qwen/Qwen3-Embedding-8B"

# Step 2: Upload content (embedding model auto-fetched from collection)
python -m app.cli upload repo https://github.com/user/repo.git my_collection

# Docker version:
docker-compose run rag-cli collections create my_collection \
  --vector-size 4096 \
  --embedding-model "Qwen/Qwen3-Embedding-8B"

docker-compose run rag-cli upload repo https://github.com/user/repo.git my_collection
```

## Usage

### Command Structure

```bash
rag-cli [global-options] <command> [command-options]
```

**Important:** Global options like `--api-token` and `--debug` must come **before** the command (upload/sync/collections), not after.

**Correct:**
```bash
rag-cli --api-token $API_TOKEN upload repo https://github.com/user/repo my_collection
```

**Incorrect:**
```bash
rag-cli upload repo --api-token $API_TOKEN https://github.com/user/repo my_collection  # ❌ Wrong!
```

**Note:** The `--model` flag is optional for uploads - the embedding model is automatically fetched from collection metadata.

### Global Options

| Option | Description | Environment Variable |
|--------|-------------|---------------------|
| `--qdrant-host` | Qdrant server host | `QDRANT_HOST` |
| `--qdrant-port` | Qdrant server port | `QDRANT_PORT` |
| `--model` | Embedding model name (optional for uploads - auto-fetched from collection) | `MODEL_NAME` |
| `--api-token` | API token for your embedding provider | `API_TOKEN` |
| `--git-token` | GitHub token | `GITHUB_TOKEN` |
| `--debug` | Enable verbose output | `DEBUG` |
| `--version` | Show version | |
| `--help` | Show help message | |

**Note:** When uploading to a collection, the `--model` flag is **optional**. The system automatically fetches the embedding model from the collection's metadata (set during collection creation). You only need to specify `--model` if the collection was created without an embedding model.

### Commands

#### Upload Commands

Upload documents (replaces/adds new content):

```bash
# Upload a single file
rag-cli upload file /path/to/document.pdf my_collection

# Upload a git repository
rag-cli upload repo https://github.com/user/repo.git my_collection

# Upload an archive
rag-cli upload archive project.tar.gz my_collection
```

#### Sync Commands

Sync documents with incremental updates (detects changes):

```bash
# Sync a single file
rag-cli sync file /path/to/document.pdf my_collection

# Sync a git repository
rag-cli sync repo https://github.com/user/repo.git my_collection

# Sync an archive
rag-cli sync archive project.tar.gz my_collection
```

#### Collection Management

```bash
# List all collections
rag-cli collections list

# Create a new collection
rag-cli collections create my_collection --vector-size 4096 --embedding-model "Qwen/Qwen3-Embedding-8B"

# Show collection info
rag-cli collections info my_collection

# Delete a collection
rag-cli collections delete my_collection
rag-cli collections delete my_collection --force  # Skip confirmation
```

## Examples

### Example 1: Create Collection and Upload

```bash
# Step 1: Create collection with embedding model
python -m app.cli collections create openai_docs \
  --vector-size 4096 \
  --embedding-model "Qwen/Qwen3-Embedding-8B"

# Step 2: Upload repository (no need to specify model again!)
python -m app.cli \
  --api-token $API_TOKEN \
  upload repo https://github.com/openai/openai-python.git openai_docs
```

### Example 2: Sync a Private Repository

```bash
# Embedding model is automatically fetched from collection metadata
python -m app.cli \
  --api-token $API_TOKEN \
  --git-token $GITHUB_TOKEN \
  sync repo https://github.com/mycompany/private-repo.git company_docs
```

### Example 3: Upload with Custom Qdrant Host

```bash
# Model is automatically fetched from collection metadata
python -m app.cli \
  --qdrant-host qdrant.example.com \
  --qdrant-port 6333 \
  --api-token $API_TOKEN \
  upload file /docs/manual.pdf product_docs
```

### Example 4: Debug Mode

```bash
python -m app.cli --debug \
  upload archive project-docs.tar.gz my_collection
```

## Docker Usage

### Using Docker Compose (Recommended)

```bash
# Start all services (Qdrant + CLI)
docker-compose up -d

# Run CLI commands
docker-compose run rag-cli collections list
docker-compose run rag-cli upload repo https://github.com/user/repo.git my_collection

# Interactive mode
docker-compose run rag-cli bash
> python -m app.cli --help

# Stop services
docker-compose down
```

### Using Docker Directly

```bash
# Build the image
docker build -t rag-cli .

# Run with environment variables
docker run \
  -e API_TOKEN=$API_TOKEN \
  -e MODEL_NAME=Qwen/Qwen3-Embedding-8B \
  -e QDRANT_HOST=host.docker.internal \
  rag-cli upload repo https://github.com/user/repo.git my_collection

# Run with env file
docker run --env-file .env rag-cli collections list

# Mount local files
docker run \
  -v $(pwd)/data:/data \
  -e API_TOKEN=$API_TOKEN \
  rag-cli upload file /data/document.pdf my_collection
```

## Supported Embedding Models

This CLI supports any embedding model compatible with your embedder. The code automatically determines which provider to use based on the model name. Simply set `API_TOKEN` to your provider's API key.

Common examples:

| Model | Provider | Dimensions |
|-------|----------|------------|
| Qwen/Qwen3-Embedding-8B | DeepInfra | 4096 |
| text-embedding-3-small | OpenAI | 1536 |
| text-embedding-3-large | OpenAI | 3072 |
| voyage-2 | Voyage AI | 1024 |
| voyage-code-2 | Voyage AI | 1536 |
| embed-english-v3.0 | Cohere | 1024 |

**Note**:
- The code determines the correct provider based on the model name
- Set `API_TOKEN` to your API key from any provider (DeepInfra, OpenAI, Cohere, Voyage AI, etc.)
- Vector size must match your collection's configuration when creating collections

## How It Works

### Upload vs Sync

- **Upload**: Processes all files and uploads to Qdrant (no change detection)
  - Use for: First-time ingestion, complete rebuilds
  - Behavior: Processes everything, may create duplicates if collection exists

- **Sync**: Intelligently detects changes using file hashes
  - Use for: Incremental updates, scheduled syncs
  - Behavior: Only processes changed/new files, removes deleted files
  - Returns: Statistics `{added: N, updated: N, deleted: N}`

### Processing Pipeline

```
Source (File/Repo/Archive)
    ↓
Git Clone / Extract (if needed)
    ↓
File Discovery & Filtering
    ↓
Semantic Chunking (via the_chunker)
    ↓
Parallel Embedding Generation
    ↓
Upload to Qdrant
```

### File Filtering

Automatically skips:
- Hidden files (`.env`, `.gitignore`, etc.)
- Build artifacts (`node_modules`, `__pycache__`, etc.)
- Binary files (unless explicitly supported like PDF)
- `.git` directories

## Configuration Priority

Settings are applied in this order (highest to lowest):

1. CLI arguments (`--model`, `--api-token`, etc.)
2. Environment variables (`MODEL_NAME`, `API_TOKEN`, etc.)
3. Default values

## Troubleshooting

### Common Issues

**API Token Not Found**
```bash
ERROR: API token is required for upload/sync operations.
```
Solution: Set `API_TOKEN` environment variable or use `--api-token` argument.

**Model Not Specified**
```bash
ERROR: Model name is required for upload/sync operations.
```
Solution: Set `MODEL_NAME` environment variable or use `--model` argument.

**Qdrant Connection Failed**
```bash
ERROR: Could not connect to Qdrant at localhost:6333
```
Solution:
- Check Qdrant is running: `docker ps | grep qdrant`
- Verify host/port with `--qdrant-host` and `--qdrant-port`
- For Docker: use `--qdrant-host qdrant`

**SSH Key Not Found (Private Repos)**
```bash
ERROR: Could not clone repository
```
Solution:
- For local: Ensure SSH keys exist in `~/.ssh/`
- For Docker: Mount SSH keys with `-v ~/.ssh:/root/.ssh:ro`
- Or use HTTPS with `--git-token $GITHUB_TOKEN`

## Development

### Project Structure

```
rag_in_aws/
├── app/
│   ├── __init__.py
│   ├── __main__.py          # Entry point for python -m app
│   ├── cli.py               # Main CLI implementation
│   ├── handlers.py          # File/Repo/Archive handlers
│   ├── qdrant_manager.py    # Qdrant operations
│   ├── embedder.py          # Embedding generation
│   ├── qdrant_chunker.py    # Chunking wrapper
│   └── git_utils.py         # Git operations
├── tests/
│   └── test_integration.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Run specific test
pytest tests/test_integration.py -v
```

### Adding New Embedding Models

The CLI is model-agnostic. To add support for new models:

1. Ensure your `embedder.py` supports the model's API
2. Use the model with `--model your-model-name`
3. Provide appropriate API token with `--api-token`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- GitHub Issues: [link to your repo]
- Documentation: [link to docs]
- Email: [your email]

## Acknowledgments

- Built with [Qdrant](https://qdrant.tech/) vector database
- Uses [the_chunker](https://github.com/yourusername/the_chunker) for semantic chunking
- Supports multiple embedding providers
