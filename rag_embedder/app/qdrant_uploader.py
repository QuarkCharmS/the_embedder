"""
Simplified upload interface for chunks to Qdrant.

Functions:
- upload_chunks_to_qdrant(): Upload chunks with smart change detection

See ARCHITECTURE.md for detailed flow and logic.
"""

from typing import List
from app.qdrant_manager import QdrantManager


def upload_chunks_to_qdrant(qdrant_chunks: List, collection_name: str, embedding_model: str, api_token: str,
                           qdrant_host: str = "localhost", qdrant_port: int = 6333):
    """
    Upload chunks to an existing Qdrant collection.

    IMPORTANT: This function assumes the collection already exists.
    It will raise an error if the collection doesn't exist.

    To create a collection first, use:
        manager = QdrantManager()
        manager.create_collection(collection_name, vector_size)

    Args:
        qdrant_chunks: List of QdrantChunk objects
        collection_name: Name of the target collection (must exist)
        embedding_model: Embedding model name (e.g., "Qwen/Qwen3-Embedding-8B")
        api_token: API token for embedding service
        qdrant_host: Qdrant server host
        qdrant_port: Qdrant server port

    Returns:
        Dict with stats: {'added': [(file, chunks)], 'modified': [(file, chunks)], 'unchanged': [(file, chunks)]}

    Raises:
        ValueError: If collection doesn't exist
    """
    manager = QdrantManager(host=qdrant_host, port=qdrant_port)
    return manager.upload_chunks_with_embeddings(
        collection_name=collection_name,
        qdrant_chunks=qdrant_chunks,
        embedding_model=embedding_model,
        api_token=api_token
    )
