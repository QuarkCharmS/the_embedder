# RAG IN AWS - HOW IT WORKS

## THE FLOW
```
Files/Repos/Archives → Handlers → Chunker → Embedder → Qdrant Vector DB
```

## ARCHITECTURE
```
ArchiveHandler (extracts .zip/.tar)
    ↓
RepoHandler (clones git, walks files)
    ↓
FileHandler (atomic unit - processes single file)
    ↓
file_to_qdrant_chunks() - smart chunking via the_chunker
    ↓
upload_chunks_to_qdrant() - generates embeddings + uploads
    ↓
Qdrant on EC2 (http://3.76.110.214:6333)
```

## KEY FILES
- **handlers.py** - FileHandler, RepoHandler, ArchiveHandler (entry points)
- **qdrant_chunker.py** - Chunks files using the_chunker, creates QdrantChunk objects
- **embedder.py** - Generates vectors via OpenAI/DeepInfra APIs
- **qdrant_manager.py** - Collection CRUD + upload operations
- **qdrant_uploader.py** - Legacy wrapper around manager

## MODELS
- text-embedding-3-small (OpenAI, 1536d) - "text" type
- text-embedding-3-large (OpenAI, 3072d)
- Qwen/Qwen3-Embedding-8B (DeepInfra, 4096d) - "code" type

## AWS INFRA
- **/infra/main.tf** - VPC (10.0.0.0/16), subnets, IGW, S3 bucket
- **/app/main.tf** - EC2 t3.medium + Qdrant Docker + 20GB EBS

## USAGE
```bash
# Create collection
python tests/test_handlers_temp.py create-collection my_docs text

# Upload file
python tests/test_handlers_temp.py file path.py my_docs text

# Upload repo
python tests/test_handlers_temp.py repo https://github.com/user/repo.git my_docs text

# Upload archive
python tests/test_handlers_temp.py archive code.zip my_docs code
```

## DEDUPLICATION
Deterministic IDs: UUID5(SHA256(file_content) + chunk_index)
→ Same file = same IDs → Qdrant upsert = no duplicates

## STATUS
✅ WORKS: Ingestion pipeline (files/repos/archives → Qdrant)
❌ MISSING: Search/retrieval, FastAPI, Lambda, file filtering, batch uploads
