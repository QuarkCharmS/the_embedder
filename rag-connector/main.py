from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
import httpx
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
    api_key=os.getenv("QDRANT_API_KEY")
)

logger.info(f"Connected to Qdrant at {os.getenv('QDRANT_URL', 'http://qdrant:6333')}")

class SearchRequest(BaseModel):
    message: str
    conversation: str
    collection_name: str
    api_key: str
    top_k: int = 5

async def get_embedding(text: str, api_key: str) -> list[float]:
    """Get embedding from DeepInfra API"""
    logger.info(f"Getting embedding for text: {text[:50]}...")
    try:
        timeout = httpx.Timeout(
            connect=10.0,   # time to establish TCP connection
            read=120.0,     # how long you're willing to wait for the model to respond
            write=30.0,
            pool=30.0,
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepinfra.com/v1/openai/embeddings",
                json={"model": "Qwen/Qwen3-Embedding-8B", "input": text},
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code == 401:
                logger.error("Invalid DeepInfra API key")
                raise HTTPException(401, "Invalid API key")

            response.raise_for_status()

            # Parse response and extract embedding
            response_data = response.json()
            logger.info("Embedding retrieved successfully")
            return response_data["data"][0]["embedding"]
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        logger.error(f"Embedding API error: {error_msg}")
        raise HTTPException(500, f"Embedding API error: {error_msg}")
    except (KeyError, IndexError) as e:
        error_msg = f"Unexpected response format: {e}. Response: {response.text[:500]}"
        logger.error(f"Embedding response parsing error: {error_msg}")
        raise HTTPException(500, f"Embedding response error: {error_msg}")
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Embedding error: {error_msg}")
        raise HTTPException(500, f"Embedding error: {error_msg}")

async def decide_intent(query: str, api_key: str) -> str:
    """Decide if query is for code or explanation"""
    logger.info("Classifying intent...")

    classification_prompt = f"""Classify this request into exactly ONE category:
- "code" if user wants to write/create/generate/fix code
- "explain" if user wants to understand/learn/get explanations

Examples:
Request: "Write a Python function to sort a list"
Answer: code

Request: "How does bubble sort work?"
Answer: explain

Request: "Create a REST API endpoint"
Answer: code

Request: "Explain what recursion means"
Answer: explain

Request: "Debug this error in my code"
Answer: code

Request: "What is the difference between SQL and NoSQL?"
Answer: explain

Now classify this request:
Request: {query}
Answer:"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            json={
                "model": "meta-llama/Llama-3.2-3B-Instruct",
                "messages": [{"role": "user", "content": classification_prompt}],
                "max_tokens": 1,
                "temperature": 0
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
        response.raise_for_status()
        intent = response.json()["choices"][0]["message"]["content"].strip().lower()
        logger.info(f"Intent: {intent}")
        return "code" if "code" in intent else "explain"

async def get_response(context: str, query: str, intent: str, api_key: str) -> str:
    """Get response from appropriate model"""
    model = "Qwen/Qwen2.5-Coder-32B-Instruct" if intent == "code" else "meta-llama/Llama-3.3-70B-Instruct"
    logger.info(f"Generating with {model}...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Use the provided context to answer the query."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuery: {query}"}
                ],
                "temperature": 0.7
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

@app.post("/search")
async def search(request: SearchRequest):
    """Embed query, search Qdrant, and generate response"""
    logger.info(f"Query: {request.message[:50]}... | Collection: {request.collection_name}")

    # Get embedding for LAST MESSAGE ONLY (for RAG search)
    try:
        embedding = await get_embedding(request.message, request.api_key)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding error: {str(e)}")
        raise HTTPException(500, f"Embedding error: {str(e)}")

    # Search Qdrant
    try:
        results = qdrant.search(
            collection_name=request.collection_name,
            query_vector=embedding,
            limit=request.top_k
        )
        logger.info(f"Found {len(results)} results")
    except Exception as e:
        logger.error(f"Qdrant error: {str(e)}")
        raise HTTPException(500, f"Qdrant error: {str(e)}")

    # Build context
    context = "\n\n".join([hit.payload.get("text", str(hit.payload)) for hit in results])

    # Classify intent and generate response using FULL CONVERSATION
    try:
        intent = await decide_intent(request.conversation, request.api_key)
        response = await get_response(context, request.conversation, intent, request.api_key)
        logger.info("Response generated")
    except Exception as e:
        logger.error(f"LLM error: {str(e)}")
        raise HTTPException(500, f"LLM error: {str(e)}")

    return {"response": response}

@app.get("/health")
def health():
    return {"status": "ok"}
