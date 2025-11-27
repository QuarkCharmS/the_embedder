"""
Universal embedding service client with auto-provider routing.

Supports OpenAI and DeepInfra models with retry logic and connection pooling.

See ARCHITECTURE.md for detailed flow and logic.
"""

import time
from typing import List

import requests

from app.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    def __init__(self, model_name: str, api_token: str):
        self.model_name = model_name
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text with retry logic.

        Supports any embedding model from DeepInfra or OpenAI:
        - Models with "/" (e.g., "Qwen/Qwen3-Embedding-8B") → DeepInfra
        - Other models (e.g., "text-embedding-3-small") → OpenAI
        """
        result = self.get_embeddings_batch([text])
        return result[0]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts in a single API call.

        This is much faster than calling get_embedding multiple times.
        Batch size is handled by the caller.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (same order as input texts)
        """
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                if "/" in self.model_name:
                    # DeepInfra batch API
                    response = self.session.post(
                        "https://api.deepinfra.com/v1/openai/embeddings",
                        json={
                            "input": texts,
                            "model": self.model_name,
                            "encoding_format": "float"
                        },
                        timeout=(10, 120)
                    )
                    response.raise_for_status()
                    data = response.json()["data"]
                    return [item["embedding"] for item in data]

                # OpenAI batch API
                response = self.session.post(
                    "https://api.openai.com/v1/embeddings",
                    json={"input": texts, "model": self.model_name},
                    timeout=(10, 120)
                )
                response.raise_for_status()
                data = response.json()["data"]
                return [item["embedding"] for item in data]

            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        "Batch API request failed (attempt %s/%s), retrying in %ss: %s",
                        attempt + 1, max_retries, wait_time, e
                    )
                    time.sleep(wait_time)
                    continue

                logger.error("Batch API request failed after %s attempts: %s", max_retries, e)
                raise

    def validate_model_exists(self) -> tuple[bool, str]:
        """
        Validate that the embedding model exists and is accessible.

        Makes a test API call with minimal text to check if the model is available.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
                - (True, "") if model exists and is accessible
                - (False, error_message) if model doesn't exist or isn't accessible
        """
        try:
            # Make a minimal test embedding request
            test_text = "test"
            _ = self.get_embeddings_batch([test_text])
            return (True, "")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                provider = "DeepInfra" if "/" in self.model_name else "OpenAI"
                return (False,
                    f"Model '{self.model_name}' not found on {provider}.\n"
                    f"Please check the model name and ensure it exists on the provider's API.\n"
                    f"Available models:\n"
                    f"  - DeepInfra: https://deepinfra.com/models/embeddings\n"
                    f"  - OpenAI: https://platform.openai.com/docs/guides/embeddings"
                )
            elif e.response.status_code == 401:
                return (False,
                    f"Authentication failed for model '{self.model_name}'.\n"
                    f"Please check your API token is valid.\n"
                    f"Set it with: export API_TOKEN=your_token_here"
                )
            elif e.response.status_code == 403:
                return (False,
                    f"Access forbidden for model '{self.model_name}'.\n"
                    f"This model may be private or require special access.\n"
                    f"Please check your API token permissions."
                )
            else:
                return (False, f"HTTP error {e.response.status_code}: {str(e)}")

        except requests.exceptions.RequestException as e:
            return (False, f"Network error while validating model: {str(e)}")

        except Exception as e:
            return (False, f"Unexpected error while validating model: {str(e)}")

    def get_vector_size(self) -> int:
        """Get vector size for the model."""
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

        raise ValueError(
            f"Unknown model '{self.model_name}'. Vector size not in lookup table.\n"
            "Please specify the vector size manually when creating your collection.\n"
            "You can find model dimensions in the provider's documentation:\n"
            "  - DeepInfra: https://deepinfra.com/models/embeddings\n"
            "  - OpenAI: https://platform.openai.com/docs/guides/embeddings"
        )
