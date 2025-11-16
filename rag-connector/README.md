# Dynamic RAG Connector

Flexible FastAPI service that receives all parameters dynamically per request. Supports any DeepInfra or OpenAI model for both embeddings and LLMs.

## How It Works

```
Request with params → Embed query → Search Qdrant → Augment prompt → Query LLM → Return response
```

**Key Features:**
- Pattern-based model routing (models with "/" → DeepInfra, others → OpenAI)
- Mix and match providers (e.g., OpenAI LLM + DeepInfra embeddings)
- Fully dynamic - no hardcoded models
- Separate API keys for embeddings and LLMs

## Setup

### Option 1: Docker (Recommended)

```bash
# Using Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t rag-connector .
docker run -d -p 8000:8000 -e QDRANT_HOST=host.docker.internal rag-connector
```

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### Option 2: Local Python

```bash
pip install -r requirements.txt
python main.py
```

Server runs at `http://localhost:8000`

## Usage

### Endpoint 1: Standard RAG Query (`/query`)

Standard endpoint with explicit parameters.

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is machine learning?",
    "model": "gpt-4",
    "api_key": "sk-...",
    "embedding_model": "text-embedding-3-small",
    "collection": "my_collection",
    "top_k": 3
  }'
```

#### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `prompt` | Yes | User's question/query |
| `model` | Yes | Any DeepInfra (with "/") or OpenAI LLM model |
| `api_key` | Yes | API key for the LLM |
| `embedding_model` | Yes | Any DeepInfra (with "/") or OpenAI embedding model |
| `collection` | Yes | Qdrant collection name to search |
| `embedding_api_key` | No | Separate key for embeddings (defaults to `api_key`) |
| `top_k` | No | Number of results (default: 3) |

#### Response Format

```json
{
  "response": "Machine learning is a subset of AI...",
  "context_used": true,
  "num_chunks": 3
}
```

---

### Endpoint 2: OpenWebUI Chat Completion (`/openwebui`)

OpenAI-compatible chat completion endpoint designed for OpenWebUI integration.

**Model Format**: `llm_model@@embedding_model@@collection_name`

The endpoint:
- Parses the model string to extract LLM model, embedding model, and collection
- Extracts API key from Authorization header
- Supports optional separate embedding API key in request body
- Returns OpenAI-compatible response

```bash
curl -X POST http://localhost:8000/openwebui \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "gpt-4@@text-embedding-3-small@@my_collection",
    "messages": [
      {"role": "user", "content": "what is in the deployment pipeline?"}
    ]
  }'
```

#### Model String Format

Format: `llm_model@@embedding_model@@collection_name`

Uses `@@` separator to avoid conflicts with model names containing hyphens or slashes.

**Examples:**

Using OpenAI for both:
- `gpt-4@@text-embedding-3-small@@my_collection`
  - LLM: `gpt-4`
  - Embedding: `text-embedding-3-small`
  - Collection: `my_collection`

Using DeepInfra for both:
- `Qwen/Qwen3-32B@@Qwen/Qwen3-Embedding-8B@@code_repo`
  - LLM: `Qwen/Qwen3-32B`
  - Embedding: `Qwen/Qwen3-Embedding-8B`
  - Collection: `code_repo`

Mixed providers (OpenAI LLM + DeepInfra embedding):
- `gpt-4o@@Qwen/Qwen3-Embedding-8B@@ml_docs`
  - LLM: `gpt-4o` (OpenAI)
  - Embedding: `Qwen/Qwen3-Embedding-8B` (DeepInfra)
  - Collection: `ml_docs`
  - Note: Requires `embedding_api_key` in request body for DeepInfra key

#### Request Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `model` | Yes | Model string in format: `llm_model@@embedding_model@@collection_name` |
| `messages` | Yes | Array of chat messages (OpenAI format) |
| `top_k` | No | Number of context chunks (default: 3) |
| `score_threshold` | No | Minimum similarity score |
| `embedding_api_key` | No | Separate API key for embeddings (if different from LLM key) |

Authorization header format: `Authorization: Bearer <llm_api_key>`

#### Response Format

OpenAI-compatible chat completion response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The deployment pipeline consists of..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

#### OpenWebUI Integration Example

In OpenWebUI, configure as an OpenAI-compatible endpoint:

1. **Base URL**: `http://localhost:8000/openwebui`
2. **API Key**: Your LLM API key (DeepInfra or OpenAI)
3. **Model Name**: Use format `llm_model@@embedding_model@@collection_name`
   - Example: `gpt-4@@text-embedding-3-small@@my_docs`
   - Example: `Qwen/Qwen3-32B@@Qwen/Qwen3-Embedding-8B@@code_repo`
   - Example: `meta-llama/Llama-3-70B-Instruct@@BAAI/bge-large-en-v1.5@@my_collection`

**Note:** If using different providers for LLM and embeddings (e.g., OpenAI LLM + DeepInfra embeddings), you'll need to configure the embedding API key separately via the request body parameter `embedding_api_key`

## Supported Models

### Embedding Models
**Any DeepInfra or OpenAI embedding model** is supported:

**DeepInfra** (models with "/" in name):
- `Qwen/Qwen3-Embedding-8B` - 4096 dims
- `BAAI/bge-large-en-v1.5` - 1024 dims
- `BAAI/bge-base-en-v1.5` - 768 dims
- `intfloat/e5-large-v2` - 1024 dims
- `sentence-transformers/all-MiniLM-L6-v2` - 384 dims
- Any other model on [DeepInfra](https://deepinfra.com/models/embeddings)

**OpenAI** (other model names):
- `text-embedding-3-small` - 1536 dims
- `text-embedding-3-large` - 3072 dims
- `text-embedding-ada-002` - 1536 dims
- Any other OpenAI embedding model

**Pattern detection**: Models containing "/" automatically route to DeepInfra, all others to OpenAI.

### LLM Models
**Any DeepInfra or OpenAI LLM** is supported:

**DeepInfra** (models with "/" in name):
- `meta-llama/Meta-Llama-3.1-70B-Instruct`
- `meta-llama/Meta-Llama-3.1-8B-Instruct`
- `Qwen/Qwen2.5-72B-Instruct`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`
- `google/gemma-2-27b-it`
- Any other model on [DeepInfra](https://deepinfra.com/models/chat)

**OpenAI**:
- `gpt-4`, `gpt-4o`, `gpt-4o-mini`
- `gpt-3.5-turbo`
- `o1`, `o1-mini`, `o1-preview`
- Any other OpenAI chat completion model

**Pattern detection**: Models containing "/" automatically route to DeepInfra, "gpt-*" and "o1*" to OpenAI.

## Configuration

Edit global settings in `main.py`:

```python
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
TOP_K = 3  # Default
SCORE_THRESHOLD = 0.7
```

## Examples

### Using OpenAI GPT-4

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain neural networks",
    "model": "gpt-4",
    "api_key": "sk-...",
    "embedding_model": "text-embedding-3-small",
    "collection": "ml_docs"
  }'
```

### Using OpenAI with DeepInfra Embeddings

```bash
# With Qwen embeddings
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Define supervised learning",
    "model": "gpt-4",
    "api_key": "sk-...",
    "embedding_model": "Qwen/Qwen3-Embedding-8B",
    "collection": "ml_docs",
    "embedding_api_key": "your-deepinfra-key"
  }'

# With BAAI/bge embeddings
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is deep learning?",
    "model": "gpt-4o",
    "api_key": "sk-...",
    "embedding_model": "BAAI/bge-large-en-v1.5",
    "collection": "ml_docs",
    "embedding_api_key": "your-deepinfra-key"
  }'
```

### Using DeepInfra LLM with DeepInfra Embeddings

```bash
# Using Llama 3.1 70B with Qwen embeddings
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain transformer architecture",
    "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "api_key": "your-deepinfra-key",
    "embedding_model": "Qwen/Qwen3-Embedding-8B",
    "collection": "ml_docs"
  }'

# Using Qwen 2.5 72B with BAAI embeddings
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is attention mechanism?",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "api_key": "your-deepinfra-key",
    "embedding_model": "BAAI/bge-large-en-v1.5",
    "collection": "ml_docs"
  }'
```

### Mixed Providers (OpenAI LLM + DeepInfra Embeddings)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is reinforcement learning?",
    "model": "gpt-4o",
    "api_key": "sk-...",
    "embedding_model": "Qwen/Qwen3-Embedding-8B",
    "collection": "ml_docs",
    "embedding_api_key": "your-deepinfra-key"
  }'
```

### Different Collection

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "How does authentication work?",
    "model": "gpt-4",
    "api_key": "sk-...",
    "embedding_model": "text-embedding-3-small",
    "collection": "security_docs",
    "top_k": 5
  }'
```

## Health Check

```bash
curl http://localhost:8000/health
```
