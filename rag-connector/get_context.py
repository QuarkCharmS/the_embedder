from typing import List, Union, Generator, Iterator
import httpx
import logging

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self):
        self.name = "My Amazing Collection"
        self.collection_name = "my_amazing_collection"
        self.api_url = "http://rag-connector:8000/search"
        self.deepinfra_api_key = "***REMOVED_API_TOKEN***"
        self.top_k = 40
    
    async def inlet(self, body: dict, user: dict) -> dict:
        """Fetch context and add it to the user's message"""
        messages = body.get("messages", [])
        
        if not messages:
            return body
        
        # Get user's last message
        user_message = messages[-1].get("content", "")
        logger.info(f"[INLET] Processing query: {user_message[:100]}...")
        
        # Fetch context from your FastAPI search endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "message": user_message,
                        "collection_name": self.collection_name,
                        "api_key": self.deepinfra_api_key,
                        "top_k": self.top_k
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                results = response.json()["results"]
                
                logger.info(f"[INLET] Retrieved {len(results)} context chunks")
                
                # Build context from results
                context = "\n\n".join([
                    f"Context {i+1} (score: {r['score']:.3f}):\n{r['payload'].get('text', str(r['payload']))}"
                    for i, r in enumerate(results)
                ])
                
                # Add context on top of user's message
                messages[-1]["content"] = f"CONTEXT:\n{context}\n\nQUERY:\n{user_message}"
                body["messages"] = messages
                
        except Exception as e:
            # If search fails, just pass through original message
            logger.error(f"[INLET] Search error: {e}")
        
        return body
