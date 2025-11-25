"""
Convert files into QdrantChunk objects for upload.

Classes:
- QdrantChunk: Represents a chunk with metadata (hash, path, content)

Functions:
- file_to_qdrant_chunks(): Chunk file and create QdrantChunk objects

See ARCHITECTURE.md for detailed flow and logic.
"""

import hashlib
import uuid
from pathlib import Path
from typing import List
from the_chunker import turn_file_to_chunks


class QdrantChunk:
    """Represents a document chunk ready for Qdrant upload."""

    def __init__(
        self,
        file_path: str,
        chunk_content: str,
        chunk_index: int,
        embedding_model: str = "Qwen/Qwen3-Embedding-8B",
        relative_path: str = None,
        file_hash: str = None
    ):
        self.file_path = file_path
        self.chunk_content = chunk_content
        self.chunk_index = chunk_index
        self.embedding_model = embedding_model
        self.relative_path = relative_path if relative_path else Path(file_path).name

        self._file_hash = file_hash if file_hash else self._create_file_hash()

        self.dict = {
            "id": self._create_id(),
            "index": self.chunk_index,
            "file_hash": self._file_hash,
            "chunk_hash": self._create_chunk_hash(),
            "content": self.chunk_content,
            "relative_path": self.relative_path
        }

    def _create_file_hash(self) -> str:
        file_content = Path(self.file_path).read_bytes()
        return hashlib.sha256(file_content).hexdigest()

    def _create_chunk_hash(self) -> str:
        return hashlib.sha256(self.chunk_content.encode()).hexdigest()

    def _create_id(self) -> str:
        uuid_string = f"{self._file_hash}_{self.chunk_index}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, uuid_string))

    def get_id(self) -> str:
        return self.dict["id"]

    def get_chunk_hash(self) -> str:
        return self.dict["chunk_hash"]

    def get_file_hash(self) -> str:
        return self.dict["file_hash"]

    def get_content(self) -> str:
        return self.dict["content"]

    def get_relative_path(self) -> str:
        return self.dict["relative_path"]


def _stream_hash_file(file_path: str) -> str:
    """Compute SHA256 hash of a file using streaming for memory efficiency."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_to_qdrant_chunks(
    file_path: str,
    embedding_model: str = "Qwen/Qwen3-Embedding-8B",
    relative_path: str = None,
    debug_level: str = "NONE"
) -> List[QdrantChunk]:
    """Turn a file into chunks ready for Qdrant upload."""
    chunks = turn_file_to_chunks(
        file_path, model_name=embedding_model, debug_level=debug_level
    )

    if chunks is None:
        raise ValueError(
            f"Unable to chunk file: {file_path}. "
            "The file may be binary, empty, or in an unsupported format. "
            "If this is an archive (.zip, .tar, .tar.gz), use 'upload archive' instead."
        )

    file_hash = _stream_hash_file(file_path)

    return [
        QdrantChunk(
            file_path, chunk["content"], index, embedding_model, relative_path, file_hash
        )
        for index, chunk in enumerate(chunks)
    ]
