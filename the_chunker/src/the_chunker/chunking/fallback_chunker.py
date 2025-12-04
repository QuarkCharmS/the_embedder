from chonkie import RecursiveChunker
from typing import List
from .tokenizer import count_tokens

MAX_CHUNKING_SIZE = 400  # Target token size per chunk

_chunker = RecursiveChunker(chunk_size=MAX_CHUNKING_SIZE)


def dumb_token_split(file_text: str, model_name: str, debug_level: str = "NONE") -> List[dict]:
    """
    Last resort: dumb character-based splitting with token estimation.

    Strategy:
    1. Count total tokens and chars
    2. Calculate chars-per-token ratio
    3. Split by character positions to create ~500 token chunks
    4. Add ~100 token overlap between chunks
    """
    if not file_text.strip():
        return []

    try:
        # Calculate token/char ratio
        total_tokens = count_tokens(file_text, model_name, debug_level)
        total_chars = len(file_text)

        if total_tokens == 0 or total_chars == 0:
            return []

        chars_per_token = total_chars / total_tokens

        # Target: 500 tokens per chunk, 100 token overlap
        target_tokens = 500
        overlap_tokens = 100

        chunk_chars = int(target_tokens * chars_per_token)
        overlap_chars = int(overlap_tokens * chars_per_token)

        if debug_level == "VERBOSE":
            print(f"[INFO] Dumb split: {total_tokens} tokens, {total_chars} chars")
            print(f"[INFO] Ratio: {chars_per_token:.2f} chars/token")
            print(f"[INFO] Chunk size: {chunk_chars} chars (~{target_tokens} tokens)")
            print(f"[INFO] Overlap: {overlap_chars} chars (~{overlap_tokens} tokens)")

        result = []
        start = 0

        while start < total_chars:
            end = min(start + chunk_chars, total_chars)
            chunk_text = file_text[start:end]

            if chunk_text.strip():
                result.append({
                    "content": chunk_text,
                    "tokens": count_tokens(chunk_text, model_name, debug_level)
                })

            # Move forward, accounting for overlap
            start += (chunk_chars - overlap_chars)

            # Prevent infinite loop if overlap >= chunk size
            if start <= (end - chunk_chars + overlap_chars):
                start = end

        if debug_level == "VERBOSE":
            print(f"[INFO] Dumb split created {len(result)} chunks")

        return result

    except Exception as e:
        if debug_level == "VERBOSE":
            print(f"[ERROR] Dumb split failed: {e}")
        return []


def fallback_chunk(file_text: str, model_name: str, debug_level: str = "NONE") -> List[dict]:
    """
    Fallback chunking with three-tier strategy:
    1. Try Chonkie (smart paragraph/sentence splitting)
    2. If Chonkie fails, try dumb token-based splitting
    3. If that fails, skip file (return empty list)
    """
    # Tier 1: Try Chonkie (smart chunking)
    try:
        chunks = _chunker(file_text)

        result = []
        for c in chunks:
            text = c.text  # preserve as-is: no strip, no whitespace removal

            if text.strip():  # only skip completely empty chunks (e.g. whitespace-only)
                result.append({
                    "content": text,              # exact content with indentation
                    "tokens": count_tokens(text, model_name, debug_level)  # count tokens on real, unmodified text
                })

        if result:  # If Chonkie produced chunks, use them
            return result

        # If Chonkie returned empty, fall through to dumb split
        if debug_level == "VERBOSE":
            print("[WARNING] Chonkie returned no chunks, trying dumb split")

    except Exception as e:
        if debug_level == "VERBOSE":
            print(f"[WARNING] Chonkie failed: {e}, trying dumb split")

    # Tier 2: Try dumb token-based splitting
    try:
        result = dumb_token_split(file_text, model_name, debug_level)
        if result:
            return result

        if debug_level == "VERBOSE":
            print("[WARNING] Dumb split returned no chunks, skipping file")

    except Exception as e:
        if debug_level == "VERBOSE":
            print(f"[ERROR] Dumb split failed: {e}, skipping file")

    # Tier 3: Give up, skip file
    return []
