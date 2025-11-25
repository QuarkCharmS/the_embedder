# RAG in AWS – The Big Project

End-to-end Retrieval-Augmented Generation stack that handles ingestion, chunking, indexing, and serving results through Open WebUI. This monorepo packages every moving part: a production-grade ingestion CLI, a reusable chunker library, a FastAPI connector for Qdrant, and local/Docker/AWS deployment assets.

## Stack Overview

- **`rag_in_aws/` – Ingestion CLI:** CLI + worker jobs that pull files, repos, or archives, chunk them with `the_chunker`, embed via your provider (DeepInfra/OpenAI/etc.), and upsert to Qdrant. Supports sync operations, SSH/HTTPS Git auth, Docker/Kubernetes/AWS Batch runtimes, and Terraform blueprints.
- **`the_chunker/` – Semantic chunking engine:** Tree-sitter aware chunker exposed as a Python package. Produces token-aware overlapping chunks and is also vendored into the CLI Docker image.
- **`rag-connector/` – Retrieval API & pipelines:** FastAPI service that embeds incoming queries, searches Qdrant, classifies intent (“code” vs “explain”), and forwards the conversation to the right DeepInfra model. Includes Open WebUI pipeline scripts to call the connector.
- **Top-level Docker Compose:** Boots Qdrant, the rag-connector, Open WebUI, and the Open WebUI pipelines service so you can demo the whole flow locally.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `rag_in_aws/app` | CLI entrypoints, handlers, embedder, Qdrant manager/uploader, git utilities |
| `rag_in_aws/docs` | Deep documentation: architecture, handler guides, Git auth, project summary |
| `rag_in_aws/terraform` | `infra/` for shared AWS networking + Batch, `app/` for job definitions |
| `the_chunker/src/the_chunker` | Chunking package used both standalone and from the CLI |
| `rag-connector/main.py` | FastAPI app exposing `POST /search` |
| `rag-connector/rag_my_query.py` | Open WebUI pipeline that proxies user chats to the connector |
| `docker-compose.yml` (root) | Spins up Open WebUI, its pipelines service, rag-connector, and Qdrant |
| `RAG-Strategy.txt`, `rag_in_aws/docs/*` | Planning docs, strategy notes, and design discussions |

## End-to-End Flow

```
┌──────────────┐   chunk+embed   ┌──────────────┐   semantic hits   ┌───────────────┐
│ Sources      │ ───────────────▶│ rag_in_aws   │──────────────────▶│   Qdrant      │
│ files/repos  │                 │ CLI/worker   │                   │  collections  │
└──────────────┘                 └──────────────┘                   └──────┬────────┘
                                                                           │
         ┌──────────────────────────────────────────────────────────────────┘
         │ context + chat
┌────────▼────────┐  REST  ┌──────────────┐  DeepInfra LLMs  ┌──────────────┐
│ Open WebUI      │───────▶│ rag-connector│─────────────────▶│ Responses     │
│ (pipelines)     │        │ FastAPI      │                  │ to the user   │
└─────────────────┘        └──────────────┘                  └──────────────┘
```

## Getting Started

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- Access token for your embedding/LLM provider (DeepInfra in the default configs)
- (Optional) AWS credentials if you plan to use the Terraform modules

### 1. Prepare the ingestion CLI

```bash
# Install the chunker locally so the CLI can import it
pip install -e the_chunker

cd rag_in_aws
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit environment template
cp .env.example .env
# Fill in MODEL_NAME, API_TOKEN, QDRANT_HOST/PORT, etc.
```

Key environment variables (can also be passed as CLI flags):

- `MODEL_NAME` – embedding model (e.g., `Qwen/Qwen3-Embedding-8B`)
- `API_TOKEN` – provider key for embeddings
- `QDRANT_HOST` / `QDRANT_PORT`
- Optional: `GITHUB_TOKEN` for private HTTPS clones, `DEBUG`, `GIT_SSH_KEY_PATH`

### 2. Create a collection & ingest content

```bash
# Inside rag_in_aws/
python -m app.cli collections create my_collection \
  --vector-size 4096 \
  --embedding-model "Qwen/Qwen3-Embedding-8B"

# Upload files/repos/archives
python -m app.cli upload repo https://github.com/user/repo.git my_collection
# or keep things fresh with incremental sync:
python -m app.cli sync repo https://github.com/user/repo.git my_collection
```

See `rag_in_aws/README.md` and `docs/` for the full command surface, runtimes (Docker, Kubernetes, AWS Batch), and troubleshooting steps.

### 3. Run the retrieval stack

```bash
# Build the rag-connector image (used by docker-compose)
cd rag-connector
docker build -t rag-connector .
cd ..

# Bring everything online
docker compose up -d

# Tail connector logs (optional)
docker compose logs -f rag-connector
```

What you get:

- Qdrant on `localhost:6333`
- rag-connector FastAPI on `localhost:8000`
- Open WebUI on `http://localhost:3000`
- Open WebUI pipelines service on `9099` (API key defaults to `***REMOVED_PIPELINES_KEY***` per compose file)

The connector expects each request to include a DeepInfra API key. When using the provided Open WebUI pipeline below, the key is read from the script.

### 4. Connect Open WebUI

1. Copy `rag-connector/rag_my_query.py` into the pipelines container:
   ```bash
   docker cp rag-connector/rag_my_query.py pipelines:/app/pipelines/rag_my_query.py
   ```
2. Edit the file (or set env vars) so `deepinfra_api_key` points to your key and `collection_name` matches the Qdrant collection you created.
3. Restart the pipelines container: `docker compose restart pipelines`.
4. In Open WebUI, enable the pipeline and start chatting. Messages flow → pipeline → rag-connector → Qdrant + DeepInfra → Open WebUI.

If you prefer to call the connector directly, send a `POST` to `http://localhost:8000/search` with:

```json
{
  "message": "last user message only",
  "conversation": "entire transcript",
  "collection_name": "my_collection",
  "api_key": "YOUR_DEEPINFRA_KEY",
  "top_k": 5
}
```

## Deployment Notes

- **Docker:** `rag_in_aws/Dockerfile` builds the CLI image (embedding `the_chunker`). `rag-connector/Dockerfile` builds the FastAPI service with health checks.
- **AWS:** `rag_in_aws/terraform/infra` provisions core infrastructure (VPC, Batch, compute environments). `rag_in_aws/terraform/app` defines job queues and containerized ingestion jobs that call the CLI worker.
- **Chunker reuse:** `the_chunker` is a standalone package – install it where you need semantic chunking (`pip install -e the_chunker` or publish it to your index). `rag_in_aws` imports it via `turn_file_to_chunks`.

## Testing & Quality

- Ingestion CLI integration tests: `cd rag_in_aws && pytest tests/`
- Chunker unit test: `cd the_chunker && pytest -q test_chunker.py`
- rag-connector manual test: `uvicorn main:app --reload` then `curl http://localhost:8000/` or `curl -X POST .../search`

## Useful References

- `rag_in_aws/README.md` – CLI usage, supported file types, Docker instructions
- `rag_in_aws/docs/` – architecture deep dives, handler details, Git auth guide, system overview
- `rag-connector/DEBUGGING.md` – verbose logging walkthroughs and troubleshooting tips
- `the_chunker/README.md` – chunker API, configuration knobs, tokenizer behavior
- `RAG-Strategy.txt` – product goals and backlog ideas

Start by ingesting a small repo with the CLI, confirm search results via `curl` against the rag-connector, then wire it into Open WebUI for an interactive RAG assistant. Once comfortable locally, promote the ingestion jobs with the Terraform modules and point them at your managed Qdrant or AWS deployment.
