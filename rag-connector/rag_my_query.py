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
    
    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        """Return RAG-based LLM response to user"""
        logger.info(f"[PIPE] Processing query: {user_message[:100]}...")

        try:
            response = httpx.post(
                self.api_url,
                json={
                    "message": user_message,
                    "collection_name": self.collection_name,
                    "api_key": self.deepinfra_api_key,
                    "top_k": self.top_k
                },
                timeout=90.0
            )
            response.raise_for_status()
            result = response.json()["response"]

            logger.info("[PIPE] Response generated")
            return result

        except Exception as e:
            logger.error(f"[PIPE] Error: {e}")
            return f"Error searching RAG: {str(e)}"
