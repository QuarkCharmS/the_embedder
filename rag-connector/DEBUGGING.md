# RAG-Connector Debugging Guide

Complete guide to debugging the rag-connector with comprehensive logging.

## What's Been Added

### Comprehensive Logging System

The rag-connector now includes detailed logging at every step:

1. **Startup Logging** - Configuration and Qdrant connection status
2. **Request Logging** - Every incoming query with full details
3. **Embedding Logging** - API calls, timing, and responses
4. **Qdrant Search Logging** - Search parameters and results with scores
5. **LLM Query Logging** - Model routing, API calls, and responses
6. **Error Logging** - Detailed error messages with context

### Log Levels

You can control logging verbosity with the `LOG_LEVEL` environment variable:

- **DEBUG**: Everything including API keys (masked), payloads, response previews
- **INFO**: Default - shows all major steps and results (recommended)
- **WARNING**: Only warnings and errors
- **ERROR**: Only errors

## How to Use

### Option 1: View Live Logs (Docker Compose)

```bash
cd /home/santiago/the_embedder/rag-connector

# Follow logs in real-time
docker-compose logs -f rag-connector

# View last 100 lines
docker-compose logs --tail 100 rag-connector

# View logs since 10 minutes ago
docker-compose logs --since 10m rag-connector
```

### Option 2: Enable DEBUG Mode

For maximum verbosity (includes API payloads, response previews):

```bash
# Stop container
docker-compose down

# Start with DEBUG logging
LOG_LEVEL=DEBUG docker-compose up -d

# Watch detailed logs
docker-compose logs -f rag-connector
```

### Option 3: Save Logs to File

```bash
# Save logs to file
docker-compose logs rag-connector > rag-connector-debug.log

# Follow and save simultaneously
docker-compose logs -f rag-connector | tee rag-connector-debug.log
```

## What You'll See in the Logs

### 1. Startup Logs

```
============================================================
RAG Connector Starting Up
============================================================
Qdrant Host: qdrant
Qdrant Port: 6333
Default TOP_K: 3
Score Threshold: 0.7
============================================================
Connecting to Qdrant at qdrant:6333...
✓ Successfully connected to Qdrant
Available collections: ['rag_in_aws_full_project', 'test_collection']
============================================================
```

**What to check:**
- ✓ Qdrant connection successful
- ✓ Collections list shows your collections

### 2. Request Start

```
================================================================================
🚀 NEW RAG QUERY REQUEST
================================================================================
Prompt: What is this about?
LLM Model: Qwen/Qwen3-32B
Embedding Model: Qwen/Qwen3-Embedding-8B
Collection: rag_in_aws_full_project
TOP_K: 3
Using separate embedding key: False
--------------------------------------------------------------------------------
```

**What to check:**
- All parameters are correct
- Model names have correct format (with "/" for DeepInfra)
- Collection name matches what's in Qdrant

### 3. Step 1: Embedding

```
Step 1/4: Embedding query...
📥 Getting embedding for text (length: 19 chars)
   Model: Qwen/Qwen3-Embedding-8B
   → Routing to DeepInfra: https://api.deepinfra.com/v1/openai/embeddings
   Response status: 200 (took 0.85s)
   ✓ Embedding generated: 4096 dimensions
```

**What to check:**
- ✓ Correct provider (DeepInfra for models with "/")
- ✓ Status 200 (success)
- ✓ Embedding dimensions match your model

**Common errors:**
- Status 401: Invalid API key
- Status 404: Model not found (check model name)
- Timeout: Network or API issues

### 4. Step 2: Qdrant Search

```
Step 2/4: Searching Qdrant...
🔍 Searching Qdrant
   Collection: rag_in_aws_full_project
   Vector dimensions: 4096
   TOP_K: 3
   Score threshold: 0.7
   ✓ Search completed in 0.05s
   Found 3 results
      [1] Score: 0.8542
      [2] Score: 0.8234
      [3] Score: 0.7891
   ✓ Assembled context: 1245 characters
```

**What to check:**
- ✓ Vector dimensions match collection
- ✓ Found results above threshold
- ✓ Scores are reasonable (0.7-1.0 is good)

**Common issues:**
- "No context found above score threshold" - Lower SCORE_THRESHOLD or check data quality
- "Collection not found" - Verify collection name
- "Dimension mismatch" - Collection was created with different embedding model

### 5. Step 3: Prompt Augmentation

```
Step 3/4: Augmenting prompt...
   ✓ Prompt augmented with context
   Final prompt length: 1342 characters
```

**What to check:**
- Context is being added to prompt
- Final prompt length is reasonable

### 6. Step 4: LLM Query

```
Step 4/4: Querying LLM...
🤖 Querying LLM
   Model: Qwen/Qwen3-32B
   Prompt length: 1342 characters
   → Routing to DeepInfra: https://api.deepinfra.com/v1/openai/chat/completions
   Response status: 200 (took 3.42s)
   ✓ LLM response received: 156 characters
```

**What to check:**
- ✓ Correct provider routing
- ✓ Status 200 (success)
- ✓ Response received

**Common errors:**
- Status 401: Invalid API key
- Status 404: Model not found or not available
- Status 429: Rate limit exceeded
- Timeout: Model taking too long (some models are slow)

### 7. Success Summary

```
================================================================================
✅ REQUEST COMPLETED SUCCESSFULLY in 4.52s
   Context used: True
   Chunks: 3
   Response length: 156 characters
================================================================================
```

**What to check:**
- Total time is reasonable
- Context was used
- Got a response

### 8. Error Example

```
================================================================================
❌ REQUEST FAILED after 2.15s
Error type: HTTPError
Error message: 404 Client Error: Not Found for url: https://api.deepinfra.com/v1/openai/chat/completions
================================================================================
```

**What to check:**
- Error type tells you what went wrong
- Error message has details
- Look at previous steps to see where it failed

## Common Issues and Solutions

### Issue 1: "Connection refused" to Qdrant

**Log shows:**
```
✗ Failed to connect to Qdrant: [Errno 111] Connection refused
```

**Solution:**
```bash
# Check Qdrant is running
docker ps | grep qdrant

# If not running, start it
docker-compose up -d qdrant

# Rebuild rag-connector
docker-compose build rag-connector
docker-compose up -d rag-connector
```

### Issue 2: "404 Model not found"

**Log shows:**
```
✗ LLM API error: 404
Response: {"error": "Model not found"}
```

**Solutions:**
1. Check model name format:
   - DeepInfra: Must have "/" (e.g., `Qwen/Qwen3-32B`)
   - OpenAI: No "/" (e.g., `gpt-4o-mini`)

2. Verify model exists:
   - DeepInfra: https://deepinfra.com/models
   - OpenAI: https://platform.openai.com/docs/models

3. Try a known working model:
   ```bash
   # DeepInfra
   "model": "meta-llama/Meta-Llama-3.1-8B-Instruct"

   # OpenAI
   "model": "gpt-4o-mini"
   ```

### Issue 3: "401 Unauthorized"

**Log shows:**
```
✗ Embedding API error: 401
Response: {"error": "Invalid API key"}
```

**Solution:**
- Verify your API key is correct
- Check you're using the right key for the right provider
- DeepInfra keys: Get from https://deepinfra.com/dash/api_keys
- OpenAI keys: Get from https://platform.openai.com/api-keys

### Issue 4: "No context found above score threshold"

**Log shows:**
```
⚠ No context found above score threshold
```

**Solutions:**
1. Lower the score threshold:
   ```bash
   SCORE_THRESHOLD=0.5 docker-compose up -d
   ```

2. Increase TOP_K:
   ```bash
   TOP_K=5 docker-compose up -d
   ```

3. Check your collection has data:
   ```bash
   curl http://localhost:6333/collections/your_collection
   ```

4. Verify you're using the same embedding model for query and data

### Issue 5: "Dimension mismatch"

**Log shows:**
```
Vector dimensions: 1536
Collection vector size: 4096
```

**Solution:**
Use the same embedding model that was used to create the collection:
- Collection with 4096 dims → Use `Qwen/Qwen3-Embedding-8B`
- Collection with 1536 dims → Use `text-embedding-3-small`
- Collection with 3072 dims → Use `text-embedding-3-large`

## Advanced Debugging

### Enable Maximum Debug Output

```bash
# Stop container
docker-compose down

# Enable DEBUG mode
LOG_LEVEL=DEBUG docker-compose up -d

# This shows:
# - API keys (masked)
# - Full request payloads
# - Response previews
# - Chunk text previews
```

### Test Individual Components

**Test embedding only:**
```python
import requests

response = requests.post(
    "https://api.deepinfra.com/v1/openai/embeddings",
    headers={"Authorization": f"Bearer YOUR_KEY"},
    json={
        "input": "test",
        "model": "Qwen/Qwen3-Embedding-8B",
        "encoding_format": "float"
    }
)
print(response.status_code, response.json())
```

**Test LLM only:**
```python
import requests

response = requests.post(
    "https://api.deepinfra.com/v1/openai/chat/completions",
    headers={"Authorization": f"Bearer YOUR_KEY"},
    json={
        "model": "Qwen/Qwen3-32B",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
print(response.status_code, response.json())
```

**Test Qdrant search:**
```bash
# Get collection info
curl http://localhost:6333/collections/your_collection

# Search with random vector
curl -X POST http://localhost:6333/collections/your_collection/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, ...],  # Use correct dimensions
    "limit": 3
  }'
```

### Save Logs for Support

```bash
# Capture full debug session
docker-compose down
LOG_LEVEL=DEBUG docker-compose up -d
sleep 5  # Let it start
docker-compose logs rag-connector > startup.log

# Make your test request
curl -X POST http://localhost:8000/query ...

# Capture the request logs
docker-compose logs rag-connector > request.log

# Include both files when asking for help
```

## Quick Checklist

Before asking for help, verify:

- [ ] Qdrant is running and accessible
- [ ] Collection exists and has data
- [ ] Model names have correct format (with "/" for DeepInfra)
- [ ] API keys are valid
- [ ] Vector dimensions match between query and collection
- [ ] Logs show where exactly the error occurs
- [ ] You have the latest container (run `docker-compose build`)

## Performance Monitoring

The logs show timing for each step:

```
Embedding: 0.85s
Search: 0.05s
LLM: 3.42s
Total: 4.52s
```

**Typical timings:**
- Embedding: 0.5-2s
- Qdrant search: 0.01-0.1s
- LLM: 2-10s (depends on model size)
- Total: 3-12s

If timings are way off, there might be network issues or the API is slow.

## Getting Help

When reporting issues, include:

1. Your request payload
2. Full error message from logs
3. Output of:
   ```bash
   docker-compose logs --tail 200 rag-connector
   curl http://localhost:8000/health
   ```

Good luck debugging! 🐛🔍
