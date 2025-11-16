"""
Dynamic RAG Connector

Flexible RAG service supporting any DeepInfra or OpenAI model.

Pattern-based routing:
- Models with "/" (e.g., "Qwen/...", "meta-llama/...") → DeepInfra
- Other models (e.g., "gpt-4", "text-embedding-3-small") → OpenAI

Receives: model, api_key, prompt, embedding_model, collection
Returns: LLM response with RAG context
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from qdrant_client import QdrantClient
from typing import Optional, List, Dict, Any
from pathlib import Path
import requests
import uvicorn
import os
import logging
import time
from datetime import datetime
import uuid
import json

# ===========================================
# LOGGING CONFIGURATION
# ===========================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ===========================================
# CONFIGURATION
# ===========================================

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# RAG Settings
TOP_K = int(os.getenv("TOP_K", "3"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.7"))

# Models configuration
MODELS_FILE = os.getenv("MODELS_FILE", "models_config/models.json")
MODELS_PATH = Path(MODELS_FILE)

def load_models_config():
    """
    Load model configurations from JSON file.
    Called on each request - allows hot-reload without server restart.
    """
    try:
        with open(MODELS_PATH, 'r') as f:
            config = json.load(f)
            # Create lookup dict: model_id -> config
            return {model['id']: model for model in config.get('models', [])}
    except FileNotFoundError:
        logger.warning(f"⚠ Models file not found: {MODELS_FILE}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"✗ Failed to parse {MODELS_FILE}: {e}")
        return {}

# Log on startup
logger.info(f"Models will be loaded from: {MODELS_PATH}")
initial_config = load_models_config()
if initial_config:
    logger.info(f"✓ Found {len(initial_config)} model(s):")
    for model_id in initial_config:
        logger.info(f"  - {model_id}")

# Log startup configuration
logger.info("=" * 60)
logger.info("RAG Connector Starting Up")
logger.info("=" * 60)
logger.info(f"Qdrant Host: {QDRANT_HOST}")
logger.info(f"Qdrant Port: {QDRANT_PORT}")
logger.info(f"Default TOP_K: {TOP_K}")
logger.info(f"Score Threshold: {SCORE_THRESHOLD}")
logger.info("=" * 60)

# ===========================================

app = FastAPI()

# Initialize Qdrant with connection logging
try:
    logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    collections = qdrant.get_collections()
    logger.info(f"✓ Successfully connected to Qdrant")
    logger.info(f"Available collections: {[c.name for c in collections.collections]}")
except Exception as e:
    logger.error(f"✗ Failed to connect to Qdrant: {e}")
    logger.error("Service will start but queries will fail until Qdrant is available")
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


class QueryRequest(BaseModel):
    prompt: str
    model: str  # LLM model: models with "/" → DeepInfra, "gpt-*"/"o1*" → OpenAI
    api_key: str  # API key for the LLM
    embedding_model: str  # Embedding model: models with "/" → DeepInfra, others → OpenAI
    collection: str  # Qdrant collection name
    embedding_api_key: str = None  # Optional separate key for embeddings (defaults to api_key)
    top_k: int = TOP_K  # Optional override
    score_threshold: float = None  # Optional score threshold (default: no filtering, returns all top_k results)


# OpenWebUI-compatible models
class ChatMessage(BaseModel):
    role: str
    content: str


class OpenWebUIRequest(BaseModel):
    model: str  # Format: "llm_model@@embedding_model@@collection_name"
    messages: List[ChatMessage]
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    embedding_api_key: Optional[str] = None  # Optional separate key for embeddings


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class OpenWebUIResponse(BaseModel):
    id: str
    object: str
    choices: List[ChatCompletionChoice]


def get_embedding(text: str, embedding_model: str, api_key: str) -> list[float]:
    """Get embedding vector for text using specified model

    Supports any embedding model from DeepInfra or OpenAI:
    - Models with "/" (e.g., "Qwen/Qwen3-Embedding-8B", "BAAI/bge-large-en-v1.5") → DeepInfra
    - Other models (e.g., "text-embedding-3-small", "text-embedding-ada-002") → OpenAI
    """
    start_time = time.time()
    logger.info(f"📥 Getting embedding for text (length: {len(text)} chars)")
    logger.info(f"   Model: {embedding_model}")

    # Mask API key for logging
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.debug(f"   API Key: {masked_key}")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Pattern-based routing: models with "/" go to DeepInfra
    if "/" in embedding_model:
        # DeepInfra (supports any HuggingFace model)
        api_url = "https://api.deepinfra.com/v1/openai/embeddings"
        provider = "DeepInfra"
        logger.info(f"   → Routing to {provider}: {api_url}")

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json={"input": text, "model": embedding_model, "encoding_format": "float"},
                timeout=60
            )
        except requests.exceptions.Timeout:
            logger.error(f"   ✗ Embedding request timed out after 60s")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"   ✗ Connection error: {e}")
            raise
    else:
        # OpenAI (supports any OpenAI embedding model)
        api_url = "https://api.openai.com/v1/embeddings"
        provider = "OpenAI"
        logger.info(f"   → Routing to {provider}: {api_url}")

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json={"input": text, "model": embedding_model},
                timeout=60
            )
        except requests.exceptions.Timeout:
            logger.error(f"   ✗ Embedding request timed out after 60s")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"   ✗ Connection error: {e}")
            raise

    # Log response details
    elapsed = time.time() - start_time
    logger.info(f"   Response status: {response.status_code} (took {elapsed:.2f}s)")

    if response.status_code != 200:
        logger.error(f"   ✗ Embedding API error: {response.status_code}")
        logger.error(f"   Response: {response.text}")
        response.raise_for_status()

    try:
        result = response.json()
        embedding = result["data"][0]["embedding"]
        logger.info(f"   ✓ Embedding generated: {len(embedding)} dimensions")
        return embedding
    except (KeyError, IndexError) as e:
        logger.error(f"   ✗ Unexpected response format: {e}")
        logger.error(f"   Response: {response.text}")
        raise


def search_qdrant(query_vector: list[float], collection: str, top_k: int, score_threshold: float = None) -> str:
    """Search Qdrant and return context as string"""
    start_time = time.time()
    logger.info(f"🔍 Searching Qdrant")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Vector dimensions: {len(query_vector)}")
    logger.info(f"   TOP_K: {top_k}")
    logger.info(f"   Score threshold: {score_threshold if score_threshold is not None else 'None (no filtering)'}")

    try:
        # Only apply score_threshold if provided
        search_params = {
            "collection_name": collection,
            "query_vector": query_vector,
            "limit": top_k,
        }
        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        results = qdrant.search(**search_params)
        elapsed = time.time() - start_time
        logger.info(f"   ✓ Search completed in {elapsed:.2f}s")
        logger.info(f"   Found {len(results)} results")

        # Log result scores
        for i, hit in enumerate(results, 1):
            logger.info(f"      [{i}] Score: {hit.score:.4f}")

    except Exception as e:
        logger.error(f"   ✗ Qdrant search failed: {e}")
        raise

    # Format context
    context_parts = []
    for i, hit in enumerate(results, 1):
        text = hit.payload.get("text", "")
        text_preview = text[:100] + "..." if len(text) > 100 else text
        logger.debug(f"   Chunk {i}: {text_preview}")
        context_parts.append(f"[{i}] {text}")

    context = "\n\n".join(context_parts) if context_parts else ""
    if context:
        logger.info(f"   ✓ Assembled context: {len(context)} characters")
    else:
        logger.warning(f"   ⚠ No context found above score threshold")

    return context


def perform_rag_query(
    user_prompt: str,
    llm_model: str,
    llm_api_key: str,
    embedding_model: str,
    embedding_api_key: str,
    collection: str,
    top_k: int = TOP_K,
    score_threshold: float = None
) -> dict:
    """
    Core RAG logic shared by all endpoints.

    Returns dict with:
        - response: LLM response text
        - context_used: bool
        - num_chunks: int
    """
    logger.info("Step 1/4: Embedding query...")
    query_vector = get_embedding(user_prompt, embedding_model, embedding_api_key)

    logger.info("Step 2/4: Searching Qdrant...")
    context = search_qdrant(query_vector, collection, top_k, score_threshold)

    logger.info("Step 3/4: Augmenting prompt...")
    if context:
        augmented_prompt = f"Context from knowledge base:\n\n{context}\n\n---\n\nUser question: {user_prompt}"
        logger.info(f"   ✓ Prompt augmented with context")
        logger.info(f"   Final prompt length: {len(augmented_prompt)} characters")
    else:
        augmented_prompt = user_prompt
        logger.warning(f"   ⚠ No context found, using original prompt")

    logger.info("Step 4/4: Querying LLM...")
    llm_response = query_llm(augmented_prompt, llm_model, llm_api_key)

    return {
        "response": llm_response,
        "context_used": bool(context),
        "num_chunks": len(context.split("\n\n")) if context else 0
    }


def query_llm(prompt: str, model: str, api_key: str) -> str:
    """Query LLM backend and return response

    Supports any LLM from DeepInfra or OpenAI:
    - Models with "/" (e.g., "meta-llama/Meta-Llama-3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct") → DeepInfra
    - Models starting with "gpt-" or "o1" (e.g., "gpt-4", "o1-preview") → OpenAI
    """
    start_time = time.time()
    logger.info(f"🤖 Querying LLM")
    logger.info(f"   Model: {model}")
    logger.info(f"   Prompt length: {len(prompt)} characters")

    # Mask API key for logging
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.debug(f"   API Key: {masked_key}")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Pattern-based routing
    if "/" in model:
        # DeepInfra (OpenAI-compatible API)
        api_url = "https://api.deepinfra.com/v1/openai/chat/completions"
        provider = "DeepInfra"
        logger.info(f"   → Routing to {provider}: {api_url}")
    elif model.startswith("gpt-") or model.startswith("o1"):
        # OpenAI
        api_url = "https://api.openai.com/v1/chat/completions"
        provider = "OpenAI"
        logger.info(f"   → Routing to {provider}: {api_url}")
    else:
        error_msg = (
            f"Unsupported LLM model: {model}.\n"
            f"Supported patterns:\n"
            f"  - OpenAI: gpt-*, o1*\n"
            f"  - DeepInfra: models with '/' (e.g., meta-llama/...)"
        )
        logger.error(f"   ✗ {error_msg}")
        raise ValueError(error_msg)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    logger.debug(f"   Request payload: {payload}")

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120
        )
    except requests.exceptions.Timeout:
        logger.error(f"   ✗ LLM request timed out after 120s")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error(f"   ✗ Connection error: {e}")
        raise

    # Log response details
    elapsed = time.time() - start_time
    logger.info(f"   Response status: {response.status_code} (took {elapsed:.2f}s)")

    if response.status_code != 200:
        logger.error(f"   ✗ LLM API error: {response.status_code}")
        logger.error(f"   Response: {response.text}")
        response.raise_for_status()

    try:
        result = response.json()
        llm_response = result["choices"][0]["message"]["content"]
        logger.info(f"   ✓ LLM response received: {len(llm_response)} characters")
        logger.debug(f"   Response preview: {llm_response[:200]}...")
        return llm_response
    except (KeyError, IndexError) as e:
        logger.error(f"   ✗ Unexpected response format: {e}")
        logger.error(f"   Response: {response.text}")
        raise


@app.post("/query")
def query_rag(req: QueryRequest):
    """
    Standard RAG endpoint with explicit parameters.

    All parameters are provided explicitly in the request body.
    """
    request_start = time.time()
    logger.info("=" * 80)
    logger.info("🚀 NEW RAG QUERY REQUEST (/query)")
    logger.info("=" * 80)
    logger.info(f"Prompt: {req.prompt[:100]}..." if len(req.prompt) > 100 else f"Prompt: {req.prompt}")
    logger.info(f"LLM Model: {req.model}")
    logger.info(f"Embedding Model: {req.embedding_model}")
    logger.info(f"Collection: {req.collection}")
    logger.info(f"TOP_K: {req.top_k}")
    logger.info(f"Score Threshold: {req.score_threshold if req.score_threshold is not None else 'None (no filtering)'}")
    logger.info(f"Using separate embedding key: {bool(req.embedding_api_key)}")
    logger.info("-" * 80)

    try:
        # Use embedding_api_key if provided, otherwise use main api_key
        embedding_key = req.embedding_api_key or req.api_key

        # Perform RAG query using shared logic
        result = perform_rag_query(
            user_prompt=req.prompt,
            llm_model=req.model,
            llm_api_key=req.api_key,
            embedding_model=req.embedding_model,
            embedding_api_key=embedding_key,
            collection=req.collection,
            top_k=req.top_k,
            score_threshold=req.score_threshold
        )

        total_elapsed = time.time() - request_start
        logger.info("=" * 80)
        logger.info(f"✅ REQUEST COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")
        logger.info(f"   Context used: {result['context_used']}")
        logger.info(f"   Chunks: {result['num_chunks']}")
        logger.info(f"   Response length: {len(result['response'])} characters")
        logger.info("=" * 80)

        return result

    except Exception as e:
        total_elapsed = time.time() - request_start
        logger.error("=" * 80)
        logger.error(f"❌ REQUEST FAILED after {total_elapsed:.2f}s")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
def list_models():
    """
    OpenAI-compatible /v1/models endpoint.

    Returns list of models defined in models.json file.
    Hot-reloads on each request - no server restart needed!
    """
    logger.info("📋 Models list requested")

    # Load models from file (hot-reload)
    models_config = load_models_config()

    # Build model list
    models = [
        {
            "id": model_config['id'],
            "object": "model",
            "owned_by": model_config.get('owned_by', 'rag-backend'),
            "created": int(time.time())
        }
        for model_config in models_config.values()
    ]

    logger.info(f"✓ Returning {len(models)} model(s): {[m['id'] for m in models]}")

    return {
        "object": "list",
        "data": models
    }


@app.post("/v1/chat/completions")
def openai_chat_completion(
    req: OpenWebUIRequest,
    authorization: Optional[str] = Header(None)
):
    """
    OpenAI-compatible /v1/chat/completions endpoint for OpenWebUI v0.6.36+

    Looks up model configuration from models.json file.
    """
    request_start = time.time()
    logger.info("=" * 80)
    logger.info("🚀 NEW CHAT COMPLETION REQUEST (/v1/chat/completions)")
    logger.info("=" * 80)

    # Extract API key from Authorization header
    if not authorization or not authorization.startswith("Bearer "):
        logger.error("Missing or invalid Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected format: 'Bearer <api_key>'"
        )

    api_key = authorization.replace("Bearer ", "").strip()
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info(f"API Key: {masked_key}")

    # Load models from file (hot-reload)
    models_config = load_models_config()

    # Look up model configuration
    model_id = req.model
    logger.info(f"Model ID: '{model_id}'")

    if model_id not in models_config:
        logger.error(f"Model not found: {model_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found. Available models: {list(models_config.keys())}"
        )

    # Get model configuration
    model_config = models_config[model_id]
    llm_model = model_config['llm_model']
    embedding_model = model_config['embedding_model']
    collection = model_config['collection']

    logger.info(f"Model Config:")
    logger.info(f"  LLM: {llm_model}")
    logger.info(f"  Embedding: {embedding_model}")
    logger.info(f"  Collection: {collection}")

    # Extract user message
    user_messages = [msg for msg in req.messages if msg.role == "user"]
    if not user_messages:
        logger.error("No user messages found")
        raise HTTPException(status_code=400, detail="No user messages found")

    user_prompt = user_messages[-1].content
    logger.info(f"User Prompt: {user_prompt[:100]}..." if len(user_prompt) > 100 else f"User Prompt: {user_prompt}")

    # Get parameters
    top_k = req.top_k if req.top_k is not None else TOP_K
    score_threshold = req.score_threshold
    embedding_api_key = req.embedding_api_key or api_key

    logger.info(f"TOP_K: {top_k}")
    logger.info(f"Score Threshold: {score_threshold if score_threshold is not None else 'None'}")
    logger.info("-" * 80)

    try:
        # Perform RAG query with config from models.json
        result = perform_rag_query(
            user_prompt=user_prompt,
            llm_model=llm_model,
            llm_api_key=api_key,
            embedding_model=embedding_model,
            embedding_api_key=embedding_api_key,
            collection=collection,
            top_k=top_k,
            score_threshold=score_threshold
        )

        # Format OpenAI-compatible response
        total_elapsed = time.time() - request_start
        response = OpenWebUIResponse(
            id=str(uuid.uuid4()),
            object="chat.completion",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=result["response"]),
                    finish_reason="stop"
                )
            ]
        )

        logger.info("=" * 80)
        logger.info(f"✅ REQUEST COMPLETED in {total_elapsed:.2f}s")
        logger.info(f"   Context used: {result['context_used']}")
        logger.info(f"   Chunks: {result['num_chunks']}")
        logger.info(f"   Response length: {len(result['response'])} characters")
        logger.info("=" * 80)

        return response

    except Exception as e:
        total_elapsed = time.time() - request_start
        logger.error("=" * 80)
        logger.error(f"❌ REQUEST FAILED after {total_elapsed:.2f}s")
        logger.error(f"Error: {type(e).__name__}: {str(e)}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    logger.debug("Root endpoint accessed")
    models_config = load_models_config()
    return {
        "status": "running",
        "service": "Dynamic RAG Connector",
        "version": "2.0.0",
        "endpoints": {
            "/query": "Standard RAG query endpoint (explicit parameters)",
            "/v1/models": "OpenAI-compatible models list (hot-reload from models.json)",
            "/v1/chat/completions": "OpenAI-compatible chat completion (for OpenWebUI)",
            "/health": "Health check endpoint"
        },
        "config": {
            "qdrant_host": QDRANT_HOST,
            "qdrant_port": QDRANT_PORT,
            "default_top_k": TOP_K,
            "score_threshold": SCORE_THRESHOLD,
            "models_file": MODELS_FILE,
            "loaded_models": list(models_config.keys())
        }
    }


@app.get("/health")
def health():
    logger.debug("Health check requested")
    try:
        collections = qdrant.get_collections()
        collection_names = [c.name for c in collections.collections]
        logger.info(f"✓ Health check passed - Qdrant connected with {len(collection_names)} collections")
        return {
            "status": "healthy",
            "qdrant": "connected",
            "collections": collection_names,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"✗ Health check failed: {e}")
        return {
            "status": "unhealthy",
            "qdrant": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting RAG Connector server on http://0.0.0.0:8000")
    logger.info("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
