import requests
from typing import List
import time
from app.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    def __init__(self, model_name: str, api_token: str):
        self.model_name = model_name
        self.api_token = api_token
        # Use session for connection pooling and reuse
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding based on model name with retry logic and timeouts

        Supports any embedding model from DeepInfra or OpenAI:
        - Models with "/" (e.g., "Qwen/Qwen3-Embedding-8B", "BAAI/bge-large-en-v1.5") → DeepInfra
        - Other models (e.g., "text-embedding-3-small", "text-embedding-ada-002") → OpenAI
        """

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Pattern-based routing: models with "/" go to DeepInfra
                if "/" in self.model_name:
                    # DeepInfra (supports any HuggingFace model)
                    response = self.session.post(
                        "https://api.deepinfra.com/v1/openai/embeddings",
                        json={
                            "input": text,
                            "model": self.model_name,
                            "encoding_format": "float"
                        },
                        timeout=(10, 60)  # (connect timeout, read timeout) in seconds
                    )
                    response.raise_for_status()
                    return response.json()["data"][0]["embedding"]

                else:
                    # OpenAI (supports any OpenAI embedding model)
                    response = self.session.post(
                        "https://api.openai.com/v1/embeddings",
                        json={"input": text, "model": self.model_name},
                        timeout=(10, 60)  # (connect timeout, read timeout) in seconds
                    )
                    response.raise_for_status()
                    return response.json()["data"][0]["embedding"]

            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"API request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API request failed after {max_retries} attempts: {e}")
                    raise

    def get_vector_size(self) -> int:
        """Get vector size for the model

        Returns the vector dimension size for known models.
        For unknown models, raises ValueError with instructions.
        """
        # Lookup table for common models
        sizes = {
            # DeepInfra models
            "Qwen/Qwen3-Embedding-8B": 4096,
            "BAAI/bge-large-en-v1.5": 1024,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-small-en-v1.5": 384,
            "intfloat/e5-large-v2": 1024,
            "intfloat/e5-base-v2": 768,
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            # OpenAI models
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

        if self.model_name in sizes:
            return sizes[self.model_name]
        else:
            raise ValueError(
                f"Unknown model '{self.model_name}'. Vector size not in lookup table.\n"
                f"Please specify the vector size manually when creating your collection.\n"
                f"You can find model dimensions in the provider's documentation:\n"
                f"  - DeepInfra: https://deepinfra.com/models/embeddings\n"
                f"  - OpenAI: https://platform.openai.com/docs/guides/embeddings"
            )
