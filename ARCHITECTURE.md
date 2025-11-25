# System Architecture

Comprehensive view of how the ingestion engine, chunker library, retrieval connector, and UI collaborate inside this monorepo.

## High-Level Flow

```mermaid
flowchart LR
    subgraph Sources
        Files[Files]
        Repos[Git Repos]
        Archives[Archives]
    end

    subgraph Ingestion[r(n)ag_embedder CLI & Worker]
        CLI[app.cli\nCommands]
        Handlers[Handlers\n(File/Repo/Archive)]
        Chunker[the_chunker\nToken-aware chunks]
        Embedder[Embedder\nExternal models]
        QdrantMgr[Qdrant Manager\nCollections/Sync]
    end

    subgraph Storage[Qdrant Vector DB]
        Collections[(Collections)]
    end

    subgraph Retrieval[rag-connector FastAPI]
        SearchAPI[/POST /search/]
        Intent[Intent Classifier]
        LLM[LLM Client\nDeepInfra/OpenAI]
    end

    subgraph UI[Open WebUI + Pipelines]
        OWUI[Open WebUI]
        Pipeline[rag_my_query.py Pipeline]
    end

    Files --> CLI
    Repos --> CLI
    Archives --> CLI
    CLI --> Handlers --> Chunker --> Embedder --> QdrantMgr --> Collections
    Pipeline -->|REST| SearchAPI --> Intent --> LLM
    SearchAPI -->|Vector search| Collections --> SearchAPI
    LLM --> OWUI
    OWUI --> Pipeline
```

## Component Details

### `rag_embedder/` – Ingestion Layer
- **CLI & Worker (`app/cli.py`, `app/__main__.py`, `app/worker.py`)**: Click-based interface plus lightweight worker entrypoint. Commands (`upload`, `sync`, `collections`) translate into job specifications runnable locally, in Docker, Kubernetes, or AWS Batch.
- **Handlers (`app/handlers.py`)**: File/Repo/Archive handlers orchestrate cloning, extraction, filtering, and per-file processing. Each handler funnels file paths into the chunking + embedding pipeline.
- **Chunking (`app/qdrant_chunker.py` + `the_chunker`)**: Wraps the standalone `the_chunker` package to convert files into deterministic `QdrantChunk` objects, computing SHA256 hashes for dedupe + sync.
- **Embedding (`app/embedder.py`)**: Calls provider APIs (OpenAI, DeepInfra, etc.) for vectors, supports batch requests, and enforces dimension/model consistency used later for collection creation.
- **Qdrant Manager (`app/qdrant_manager.py`)**: Owns collection lifecycle and batch upserts. Implements incremental sync using file + chunk hashes so only changes incur embedding costs. Delegates actual upload batches to `qdrant_uploader.py`.
- **Git utilities (`app/git_utils.py`)**: Smart SSH/HTTPS cloning with token detection, optional key mounting for container deployments.
- **Terraform (`terraform/infra`, `terraform/app`)**: Infrastructure blueprints for AWS networking + Batch queues to run ingestion jobs remotely.

### `the_chunker/` – Chunking Library
- Tree-sitter-aware semantic chunking with fallback strategies.
- Token-aware overlap merging tuned for large embedding windows (defaults: Qwen/Qwen3-Embedding-8B).
- Exported as a pip-installable package so the CLI Docker image and external consumers share the logic.

### `rag-connector/` – Retrieval & Generation
- **FastAPI (`main.py`)**: Exposes `/search`, embeds the latest user message, queries Qdrant, fuses the top-K payloads, and runs a lightweight intent classifier to choose between “code” vs “explain” model families.
- **Pipeline scripts (`rag_my_query.py`)**: Open WebUI integration that packages the user conversation, calls the connector, and streams the generated reply back into WebUI.
- **Dockerfile + docker-compose**: Builds slim FastAPI image with health checks, and the root-level compose file runs rag-connector alongside Qdrant, Open WebUI, and the Open WebUI pipelines service.

### Supporting Services
- **Qdrant**: Vector storage for embeddings produced during ingestion; each collection stores metadata hashes for sync.
- **Open WebUI + Pipelines**: Chat UI layer that routes messages through a small Python pipeline to call the rag-connector, enabling conversational RAG.

## Execution Paths

1. **Ingestion (Batch or CLI)**  
   - User runs `python -m app.cli upload ...` or a scheduled AWS Batch job.  
   - Handler clones/extracts sources, filters files, and feeds them into `the_chunker`.  
   - Chunk payloads are embedded via configured model, batched uploads hit Qdrant, and the collection metadata (model name, dimensions) is stored for downstream use.

2. **Retrieval (Interactive)**  
   - User chats in Open WebUI; the `rag_my_query` pipeline forwards the entire conversation plus last message to rag-connector.  
   - Connector embeds the last message, performs vector search against the relevant Qdrant collection, classifies intent, and calls the matching DeepInfra/OpenAI model with both context and conversation.  
   - Response flows back through the pipeline to Open WebUI.

3. **Infrastructure**  
   - Local development: use `docker compose` at the repo root to bring up Qdrant, rag-connector, and Open WebUI.  
   - Production: Terraform modules spin up AWS networking, ECR images, and Batch queues; ingestion jobs run as containers while rag-connector can be deployed to ECS/Kubernetes alongside managed Qdrant.

Use this document as the canonical reference when reasoning about integrations, deployment targets, or cross-cutting changes across the CLI, chunker, and retrieval layers.
