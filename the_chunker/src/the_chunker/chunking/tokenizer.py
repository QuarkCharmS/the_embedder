import os
from typing import List, Dict

# Import OpenAI-specific tokenization logic from the strategy module
from .tokenizer_strategy import is_openai_model, count_tokens_openai

# Import lightweight HuggingFace tokenizer fetcher
from .tokenizer_fetcher import get_hf_tokenizer

# Optional: transformers fallback (only loaded if USE_TRANSFORMERS_FALLBACK=1)
try:
    from transformers import AutoTokenizer
    from transformers.utils import RepositoryNotFoundError
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    RepositoryNotFoundError = Exception  # Dummy for type hints

# This tokenizer module supports both OpenAI models (using tiktoken) and HuggingFace models.
# For OpenAI models: uses tiktoken for accurate token counting (via tokenizer_strategy)
# For HuggingFace models: uses lightweight tokenizer fetcher (tokenizers/sentencepiece)
#   with optional fallback to AutoTokenizer if USE_TRANSFORMERS_FALLBACK=1

# Global tokenizer cache to avoid reloading for every chunk
_tokenizer_cache = {}

def count_tokens(text: str, model_name: str, debug_level: str = "NONE") -> int:
    """
    Count the number of tokens in a single string.

    Supports both:
    - OpenAI models (gpt-4, gpt-3.5-turbo, o1, text-embedding-*, etc.) via tiktoken
    - HuggingFace models (Qwen, LLaMA, etc.) via AutoTokenizer

    Args:
        text: Text to tokenize
        model_name: Name of the model (OpenAI or HuggingFace)
        debug_level: Debug verbosity level ("VERBOSE" for detailed output)

    No special tokens like [CLS] or [SEP] are added—this is raw count.
    """
    # Route to appropriate tokenizer based on model type
    if is_openai_model(model_name):
        return count_tokens_openai(text, model_name, debug_level)

    # HuggingFace tokenizer path - check cache first
    if model_name in _tokenizer_cache:
        tokenizer_wrapper = _tokenizer_cache[model_name]
    else:
        try:
            # Get HuggingFace token from environment if available
            hf_token = os.getenv('HF_TOKEN') or os.getenv('HUGGING_FACE_HUB_TOKEN')

            # Use lightweight tokenizer fetcher (tokenizers/sentencepiece)
            # Falls back to transformers if USE_TRANSFORMERS_FALLBACK=1
            tokenizer_wrapper = get_hf_tokenizer(
                model_name=model_name,
                token=hf_token,
                use_transformers_fallback=os.getenv('USE_TRANSFORMERS_FALLBACK', '0') == '1'
            )
            _tokenizer_cache[model_name] = tokenizer_wrapper  # Cache it for next time

            if debug_level == "VERBOSE":
                print(f"[INFO] Loaded tokenizer for '{model_name}' (type: {tokenizer_wrapper.tokenizer_type})")

        except Exception as e:
            # Provide helpful error messages
            error_msg = str(e)
            if "not found" in error_msg.lower() or "404" in error_msg:
                print(f"Model '{model_name}' not found on HuggingFace Hub")
            elif "401" in error_msg:
                print("Authentication required - set HF_TOKEN environment variable")
            elif "403" in error_msg:
                print("Access forbidden - private model or invalid token")
            elif "connection" in error_msg.lower():
                print("Network connection failed")
            elif "missing" in error_msg.lower() or "import" in error_msg.lower():
                print(f"Missing dependency: {error_msg}")
            else:
                print(f"Error loading tokenizer: {error_msg}")
            raise

    # Count tokens using the wrapper's count_tokens method
    return tokenizer_wrapper.count_tokens(text, add_special_tokens=False)

def assign_tokens_to_blocks(blocks: List[str], model_name: str, debug_level: str = "NONE") -> List[Dict]:
    """
    Take a list of text blocks (e.g., code chunks) and return a list of dictionaries,
    where each dict contains the original text and its token count.

    Args:
        blocks: List of text blocks to tokenize
        model_name: Name of the model (OpenAI or HuggingFace)
        debug_level: Debug verbosity level ("VERBOSE" for detailed output)

    Useful for deciding how to chunk content later based on token limits.
    """
    return [
        {
            "text": block,               # Original code/text block
            "tokens": count_tokens(block, model_name, debug_level)  # How many tokens the model sees in this block
        }
        for block in blocks
    ]

