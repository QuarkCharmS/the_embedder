"""
Lightweight tokenizer fetcher for HuggingFace models.

This module provides a way to download and cache tokenizers without the heavy
transformers/torch dependencies. It uses:
- huggingface_hub for downloading tokenizer files
- tokenizers library for BPE/WordPiece tokenizers
- sentencepiece for SentencePiece tokenizers

The tokenizers are cached locally in ~/.cache/the_chunker/<model_name>/ for faster
loading on subsequent runs.
"""

import os
import json
from pathlib import Path
from typing import Union, Optional, Dict, Any
import logging

try:
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import HfHubHTTPError, RepositoryNotFoundError
except ImportError:
    raise ImportError(
        "huggingface_hub is required for tokenizer fetching. "
        "Install it with: pip install huggingface_hub"
    )

try:
    from tokenizers import Tokenizer as HFTokenizer
except ImportError:
    HFTokenizer = None

try:
    import sentencepiece as spm
except ImportError:
    spm = None

# Optional: transformers as fallback
try:
    from transformers import AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


logger = logging.getLogger(__name__)


class TokenizerWrapper:
    """
    Unified wrapper for different tokenizer types.

    This provides a consistent interface for counting tokens regardless of
    whether the underlying tokenizer is from the `tokenizers` library or
    SentencePiece.
    """

    def __init__(self, tokenizer, tokenizer_type: str):
        """
        Initialize the wrapper.

        Args:
            tokenizer: The underlying tokenizer object
            tokenizer_type: Type of tokenizer ("hf_tokenizers", "sentencepiece", "transformers")
        """
        self.tokenizer = tokenizer
        self.tokenizer_type = tokenizer_type

    def encode(self, text: str, add_special_tokens: bool = False) -> list:
        """
        Encode text to token IDs.

        Args:
            text: Text to encode
            add_special_tokens: Whether to add special tokens like [CLS], [SEP]

        Returns:
            List of token IDs
        """
        if self.tokenizer_type == "hf_tokenizers":
            # tokenizers.Tokenizer
            encoding = self.tokenizer.encode(text, add_special_tokens=add_special_tokens)
            return encoding.ids

        elif self.tokenizer_type == "sentencepiece":
            # SentencePiece
            # Note: SentencePiece doesn't have add_special_tokens, it always includes BOS/EOS if configured
            # For token counting, we typically want just the content tokens
            return self.tokenizer.encode(text, out_type=int)

        elif self.tokenizer_type == "tiktoken":
            # tiktoken Encoding (fallback for unknown models)
            return self.tokenizer.encode(text)

        elif self.tokenizer_type == "transformers":
            # transformers AutoTokenizer (fallback)
            return self.tokenizer.encode(text, add_special_tokens=add_special_tokens)

        else:
            raise ValueError(f"Unknown tokenizer type: {self.tokenizer_type}")

    def count_tokens(self, text: str, add_special_tokens: bool = False) -> int:
        """
        Count the number of tokens in text.

        Args:
            text: Text to count tokens for
            add_special_tokens: Whether to include special tokens in count

        Returns:
            Number of tokens
        """
        return len(self.encode(text, add_special_tokens=add_special_tokens))


def get_cache_dir(model_name: str, cache_dir: Optional[str] = None) -> Path:
    """
    Determine the cache directory for a model's tokenizer files.

    Args:
        model_name: HuggingFace model name (e.g., "bert-base-uncased")
        cache_dir: Optional custom cache directory. If None, uses ~/.cache/the_chunker/

    Returns:
        Path to the cache directory for this model
    """
    if cache_dir:
        base_dir = Path(cache_dir)
    else:
        base_dir = Path.home() / ".cache" / "the_chunker"

    # Sanitize model name for filesystem (replace / with --)
    safe_model_name = model_name.replace("/", "--")
    model_cache_dir = base_dir / safe_model_name
    model_cache_dir.mkdir(parents=True, exist_ok=True)

    return model_cache_dir


def download_tokenizer_files(
    model_name: str,
    token: Optional[str] = None
) -> Dict[str, Path]:
    """
    Download tokenizer files from HuggingFace Hub.

    This downloads the minimal set of files needed for tokenization:
    - tokenizer_config.json (to understand tokenizer type)
    - tokenizer.json (for fast tokenizers)
    - vocab.json, merges.txt (for BPE tokenizers without tokenizer.json)
    - tokenizer.model or spiece.model (for SentencePiece)
    - added_tokens.json (if present)

    Args:
        model_name: HuggingFace model name
        token: Optional HuggingFace API token for private models

    Returns:
        Dictionary mapping file types to their local paths
    """
    downloaded_files = {}

    # Files to attempt downloading (in order of preference)
    file_priority = [
        "tokenizer_config.json",   # Always needed to understand tokenizer type
        "tokenizer.json",           # Fast tokenizer (preferred for BPE/WordPiece)
        "vocab.json",               # Vocabulary for BPE
        "merges.txt",               # Merges for BPE
        "tokenizer.model",          # SentencePiece model
        "spiece.model",             # Alternative SentencePiece name
        "added_tokens.json",        # Additional tokens
    ]

    # tokenizer_config.json is REQUIRED - but we'll gracefully handle failures
    try:
        print(f"[DEBUG] Downloading tokenizer_config.json for {model_name}")
        local_path = hf_hub_download(
            repo_id=model_name,
            filename="tokenizer_config.json",
            token=token,
            local_files_only=False,
        )
        downloaded_files["tokenizer_config.json"] = Path(local_path)
        print(f"[DEBUG] Successfully downloaded tokenizer_config.json")
    except HfHubHTTPError as e:
        import sys
        if "401" in str(e):
            print(f"[WARNING] Model '{model_name}' requires authentication.", file=sys.stderr)
            print(f"[WARNING] Set HF_TOKEN environment variable to access private models.", file=sys.stderr)
            print(f"[WARNING] Get your token from: https://huggingface.co/settings/tokens", file=sys.stderr)
        elif "404" in str(e):
            print(f"[WARNING] Model '{model_name}' not found on HuggingFace Hub.", file=sys.stderr)
            print(f"[WARNING] Please check the model name at: https://huggingface.co/models", file=sys.stderr)
        else:
            print(f"[WARNING] Failed to download tokenizer for '{model_name}': {e}", file=sys.stderr)

        # Return empty dict - will trigger fallback in get_hf_tokenizer()
        return {}
    except Exception as e:
        import sys
        print(f"[WARNING] Failed to download tokenizer for '{model_name}': {e}", file=sys.stderr)
        # Return empty dict - will trigger fallback in get_hf_tokenizer()
        return {}

    # Now download optional files (these can fail without breaking)
    for filename in file_priority[1:]:  # Skip tokenizer_config.json (already downloaded)
        try:
            print(f"[DEBUG] Attempting to download {filename} for {model_name}")
            local_path = hf_hub_download(
                repo_id=model_name,
                filename=filename,
                token=token,
                local_files_only=False,
            )
            downloaded_files[filename] = Path(local_path)
            print(f"[DEBUG] Successfully downloaded {filename}")
        except Exception as e:
            # Optional files - just log and continue
            print(f"[DEBUG] File {filename} not available: {e}")
            continue

    print(f"[DEBUG] Downloaded files: {list(downloaded_files.keys())}")
    return downloaded_files


def detect_tokenizer_type(config: Dict[str, Any], files: Dict[str, Path]) -> str:
    """
    Detect the type of tokenizer based on config and available files.

    Args:
        config: tokenizer_config.json contents
        files: Dictionary of downloaded files

    Returns:
        One of: "sentencepiece", "bpe", "wordpiece", "unknown"
    """
    # Check tokenizer_class in config
    tokenizer_class = config.get("tokenizer_class", "").lower()

    # SentencePiece indicators
    if "sentencepiece" in tokenizer_class or "llama" in tokenizer_class or "t5" in tokenizer_class:
        return "sentencepiece"

    if "tokenizer.model" in files or "spiece.model" in files:
        return "sentencepiece"

    # BPE indicators
    if "gpt" in tokenizer_class or "roberta" in tokenizer_class or "qwen" in tokenizer_class:
        return "bpe"

    # WordPiece indicators
    if "bert" in tokenizer_class or "distilbert" in tokenizer_class:
        return "wordpiece"

    # Check model_type
    model_type = config.get("model_type", "").lower()
    if "llama" in model_type or "t5" in model_type or "xlnet" in model_type:
        return "sentencepiece"

    if "gpt" in model_type or "roberta" in model_type or "qwen" in model_type:
        return "bpe"

    if "bert" in model_type:
        return "wordpiece"

    # If we have tokenizer.json, we can use the fast tokenizers library
    if "tokenizer.json" in files:
        return "bpe"  # Most fast tokenizers are BPE-like

    return "unknown"


def load_tokenizer_from_files(
    files: Dict[str, Path],
    tokenizer_type: str,
    config: Dict[str, Any]
) -> Union[HFTokenizer, "spm.SentencePieceProcessor"]:
    """
    Load a tokenizer from downloaded files.

    Args:
        files: Dictionary of downloaded file paths
        tokenizer_type: Type of tokenizer ("sentencepiece", "bpe", "wordpiece")
        config: tokenizer_config.json contents

    Returns:
        Loaded tokenizer object (either tokenizers.Tokenizer or SentencePieceProcessor)

    Raises:
        ValueError: If tokenizer cannot be loaded
    """
    # Try loading with tokenizers library (for BPE/WordPiece)
    if "tokenizer.json" in files and HFTokenizer is not None:
        try:
            tokenizer = HFTokenizer.from_file(str(files["tokenizer.json"]))
            logger.info(f"Loaded tokenizer from tokenizer.json using tokenizers library")
            return tokenizer
        except Exception as e:
            logger.warning(f"Failed to load tokenizer.json: {e}")

    # Try loading SentencePiece
    if tokenizer_type == "sentencepiece":
        if spm is None:
            raise ImportError(
                "sentencepiece is required for SentencePiece tokenizers. "
                "Install it with: pip install sentencepiece"
            )

        # Find the SentencePiece model file
        sp_model_path = files.get("tokenizer.model") or files.get("spiece.model")
        if sp_model_path:
            try:
                sp = spm.SentencePieceProcessor()
                sp.load(str(sp_model_path))
                logger.info(f"Loaded SentencePiece tokenizer from {sp_model_path.name}")
                return sp
            except Exception as e:
                logger.error(f"Failed to load SentencePiece model: {e}")
                raise ValueError(f"Failed to load SentencePiece tokenizer: {e}")
        else:
            raise ValueError("SentencePiece tokenizer detected but no model file found")

    # If we have vocab.json and merges.txt, try to construct a BPE tokenizer
    if "vocab.json" in files and "merges.txt" in files and HFTokenizer is not None:
        try:
            from tokenizers import Tokenizer
            from tokenizers.models import BPE

            # Load vocab and merges
            with open(files["vocab.json"], "r", encoding="utf-8") as f:
                vocab = json.load(f)

            with open(files["merges.txt"], "r", encoding="utf-8") as f:
                merges = [line.strip() for line in f if line.strip() and not line.startswith("#")]

            # Create BPE model
            bpe = BPE(vocab=vocab, merges=merges)
            tokenizer = Tokenizer(bpe)
            logger.info("Loaded BPE tokenizer from vocab.json and merges.txt")
            return tokenizer
        except Exception as e:
            logger.warning(f"Failed to construct BPE tokenizer from vocab/merges: {e}")

    raise ValueError(
        f"Could not load tokenizer of type '{tokenizer_type}'. "
        f"Available files: {list(files.keys())}. "
        "Consider installing transformers for fallback support."
    )


def get_tiktoken_fallback(model_name: str) -> TokenizerWrapper:
    """
    Create a tiktoken-based tokenizer as fallback.

    Uses GPT-4's cl100k_base encoding as a reasonable default for unknown models.
    Logs warning to inform user that approximate tokenization is being used.

    Args:
        model_name: Name of the model that failed to load

    Returns:
        TokenizerWrapper wrapping a tiktoken encoding
    """
    try:
        import tiktoken
    except ImportError:
        raise ImportError(
            "tiktoken is required for fallback tokenization. "
            "Install it with: pip install tiktoken"
        )

    import sys

    # Use cl100k_base (GPT-4) as default - good balance of vocabulary size
    encoding = tiktoken.get_encoding("cl100k_base")

    print(f"[WARNING] Tokenizer for '{model_name}' not available.", file=sys.stderr)
    print(f"[WARNING] Falling back to tiktoken (cl100k_base) for approximate token counting.", file=sys.stderr)
    print(f"[WARNING] Token counts may differ from actual model. This is acceptable for RAG chunking.", file=sys.stderr)

    return TokenizerWrapper(encoding, "tiktoken")


def get_hf_tokenizer(
    model_name: str,
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
    use_transformers_fallback: bool = None
) -> TokenizerWrapper:
    """
    Get a lightweight HuggingFace tokenizer without loading transformers/torch.

    This function downloads minimal tokenizer files from HuggingFace Hub and loads
    them using lightweight libraries (tokenizers, sentencepiece) instead of the
    heavy transformers library.

    The tokenizer files are cached automatically by huggingface_hub (typically in
    ~/.cache/huggingface/hub/) for faster loading on subsequent runs.

    Args:
        model_name: HuggingFace model name (e.g., "bert-base-uncased", "meta-llama/Llama-2-7b")
        cache_dir: Optional custom cache directory (currently unused, reserved for future use)
        token: Optional HuggingFace API token for private models
        use_transformers_fallback: Whether to fall back to transformers if lightweight
            loading fails. If None, uses env var USE_TRANSFORMERS_FALLBACK (default: False)

    Returns:
        TokenizerWrapper: A wrapper around the loaded tokenizer with a consistent API

    Raises:
        ValueError: If tokenizer cannot be loaded and fallback is disabled
        ImportError: If required dependencies are missing

    Examples:
        >>> tokenizer = get_hf_tokenizer("bert-base-uncased")
        >>> count = tokenizer.count_tokens("Hello world", add_special_tokens=False)
        >>> print(count)
        2
    """
    # Determine if we should use transformers fallback
    if use_transformers_fallback is None:
        use_transformers_fallback = os.getenv("USE_TRANSFORMERS_FALLBACK", "0") == "1"

    # Download tokenizer files (hf_hub_download handles caching automatically)
    logger.debug(f"Fetching tokenizer files for {model_name}...")
    files = download_tokenizer_files(model_name, token)

    # If download failed (empty dict), fall back to tiktoken
    if not files:
        if use_transformers_fallback and TRANSFORMERS_AVAILABLE:
            logger.warning(
                f"No tokenizer files found for {model_name}, "
                "falling back to transformers AutoTokenizer"
            )
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, token=token)
                return TokenizerWrapper(tokenizer, "transformers")
            except Exception as e:
                logger.warning(f"Transformers fallback also failed: {e}")
                return get_tiktoken_fallback(model_name)
        else:
            # Use tiktoken fallback
            logger.warning(f"No tokenizer files found for {model_name}, using tiktoken fallback")
            return get_tiktoken_fallback(model_name)

    # Load tokenizer config
    if "tokenizer_config.json" not in files:
        if use_transformers_fallback and TRANSFORMERS_AVAILABLE:
            logger.warning(
                f"No tokenizer_config.json found for {model_name}, "
                "falling back to transformers AutoTokenizer"
            )
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, token=token)
                return TokenizerWrapper(tokenizer, "transformers")
            except Exception as e:
                logger.warning(f"Transformers fallback also failed: {e}")
                return get_tiktoken_fallback(model_name)
        else:
            # Use tiktoken fallback
            logger.warning(f"No tokenizer_config.json found for {model_name}, using tiktoken fallback")
            return get_tiktoken_fallback(model_name)

    with open(files["tokenizer_config.json"], "r", encoding="utf-8") as f:
        config = json.load(f)

    # Detect tokenizer type
    tokenizer_type = detect_tokenizer_type(config, files)
    logger.debug(f"Detected tokenizer type: {tokenizer_type}")

    # Try to load the tokenizer
    try:
        tokenizer = load_tokenizer_from_files(files, tokenizer_type, config)

        # Wrap based on type
        if isinstance(tokenizer, HFTokenizer):
            return TokenizerWrapper(tokenizer, "hf_tokenizers")
        elif spm and isinstance(tokenizer, spm.SentencePieceProcessor):
            return TokenizerWrapper(tokenizer, "sentencepiece")
        else:
            raise ValueError(f"Unknown tokenizer type returned: {type(tokenizer)}")

    except (ValueError, ImportError) as e:
        # If lightweight loading failed, try transformers fallback
        if use_transformers_fallback and TRANSFORMERS_AVAILABLE:
            logger.warning(
                f"Lightweight tokenizer not supported for '{model_name}'. "
                "Falling back to transformers AutoTokenizer"
            )
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, token=token)
                return TokenizerWrapper(tokenizer, "transformers")
            except Exception as e2:
                logger.warning(f"Transformers fallback also failed: {e2}")
                return get_tiktoken_fallback(model_name)
        else:
            # Use tiktoken fallback instead of raising exception
            logger.warning(f"Failed to load lightweight tokenizer for '{model_name}': {e}")
            return get_tiktoken_fallback(model_name)
