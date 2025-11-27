# Tokenizer Strategy Guide

This guide explains how `the_chunker` handles tokenization for different embedding models, including the default behavior, fallback strategies, and how to control them.

---

## Overview

The tokenizer system in `the_chunker` is designed to be **lightweight by default** with **automatic fallbacks** to ensure it always works, even when the exact tokenizer for your model isn't available.

**Key Principle**: For RAG chunking, approximate token counts are acceptable. The system prioritizes reliability over perfect accuracy.

---

## Default Behavior (Lightweight)

By default, `the_chunker` uses **minimal dependencies** and **automatic fallbacks**:

```python
from the_chunker.chunking.tokenizer import count_tokens

# Works automatically - no configuration needed
token_count = count_tokens("Hello world", "Qwen/Qwen3-Embedding-8B")
```

### What Happens Automatically

1. **OpenAI models** (e.g., `text-embedding-3-small`, `gpt-4`)
   - Uses `tiktoken` library (fast, lightweight, accurate)
   - No downloads needed
   - Always works ✅

2. **HuggingFace models** (e.g., `Qwen/Qwen3-Embedding-8B`, `BAAI/bge-large-en-v1.5`)
   - **First**: Tries to download lightweight tokenizer files
   - Downloads only tokenizer files (not model weights)
   - Uses lightweight libraries: `tokenizers` or `sentencepiece`
   - Caches files in `~/.cache/huggingface/hub/`

3. **Unknown/Unavailable models**
   - **Fallback**: Uses `tiktoken` with GPT-4's encoding (cl100k_base)
   - Shows warnings but continues processing
   - Provides approximate token counts (acceptable for RAG)

---

## Fallback Hierarchy

The tokenizer system has a **three-tier fallback** strategy:

```
┌─────────────────────────────────────────┐
│ Tier 1: Native Tokenizer               │
│ - OpenAI → tiktoken                     │
│ - HuggingFace → lightweight download    │
└─────────────────────────────────────────┘
                  ↓ (if download fails)
┌─────────────────────────────────────────┐
│ Tier 2: Tiktoken Fallback (Default)    │
│ - Uses cl100k_base encoding             │
│ - Shows warnings                        │
│ - Approximate counts (good for RAG)     │
└─────────────────────────────────────────┘
                  ↓ (if explicitly enabled)
┌─────────────────────────────────────────┐
│ Tier 3: Transformers (Heavy, Optional) │
│ - Uses transformers.AutoTokenizer       │
│ - Requires torch + transformers (~4GB)  │
│ - Most accurate for custom models       │
└─────────────────────────────────────────┘
```

---

## When Each Tier is Used

### Tier 1: Native Tokenizer (Default)

**OpenAI Models:**
```python
count_tokens("text", "text-embedding-3-small")  # Uses tiktoken
count_tokens("text", "gpt-4")                   # Uses tiktoken
```
- No setup needed
- Always works
- 100% accurate

**HuggingFace Models with Available Tokenizers:**
```python
count_tokens("text", "Qwen/Qwen3-Embedding-8B")     # Downloads & caches
count_tokens("text", "BAAI/bge-large-en-v1.5")      # Downloads & caches
```
- First call: Downloads tokenizer files
- Subsequent calls: Uses cached files
- Very accurate (model's actual tokenizer)

### Tier 2: Tiktoken Fallback (Automatic)

**Triggered when:**
- Model doesn't exist on HuggingFace (404 error)
- Model requires authentication but no token provided (401 error)
- Network error during download
- HF_TOKEN not set for private models

**Example output:**
```
[WARNING] Model 'nonexistent/model' not found on HuggingFace Hub.
[WARNING] Falling back to tiktoken (cl100k_base) for approximate token counting.
[WARNING] Token counts may differ from actual model. This is acceptable for RAG chunking.
```

**When this is acceptable:**
- RAG chunking (semantic meaning preserved)
- Exploratory work
- Testing with placeholder model names

**When this might be problematic:**
- Exact token limits are critical
- Billing based on precise token counts

### Tier 3: Transformers Fallback (Opt-in)

**How to enable:**
```bash
# Install heavy dependencies
pip install -e ".[transformers]"

# Enable transformers fallback
export USE_TRANSFORMERS_FALLBACK=1
```

**When to use:**
- Custom tokenizers requiring `trust_remote_code=True`
- Models not supported by lightweight tokenizers
- Need maximum accuracy for unusual models

**Trade-offs:**
- ✅ Most compatible
- ✅ Supports custom tokenizers
- ❌ Heavy dependencies (~4GB for torch + transformers)
- ❌ Slower installation
- ❌ Slower first load

---

## Configuration Examples

### Example 1: Default (Lightweight)
```bash
# Install minimal dependencies
pip install -e .

# Just use it - fallbacks happen automatically
python -m the_chunker.chunker input.py
```

**Dependencies**: `~40MB` (tiktoken, huggingface_hub, tokenizers, sentencepiece)

### Example 2: Private HuggingFace Models
```bash
# Set HuggingFace token
export HF_TOKEN=hf_your_token_here

# Use private models
python -c "from the_chunker.chunking.tokenizer import count_tokens; \
           print(count_tokens('test', 'your-org/private-model'))"
```

### Example 3: Transformers Fallback (Heavy)
```bash
# Install with transformers support
pip install -e ".[transformers]"

# Enable transformers fallback
export USE_TRANSFORMERS_FALLBACK=1

# Now uses transformers if lightweight fails
python -m the_chunker.chunker input.py
```

**Dependencies**: `~4GB` (includes torch, transformers)

### Example 4: Custom Cache Location
```bash
# Change HuggingFace cache directory
export HF_HOME=/custom/cache/path
# or
export HUGGINGFACE_HUB_CACHE=/custom/cache/path

# Tokenizers will cache to /custom/cache/path
python -m the_chunker.chunker input.py
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `HF_TOKEN` | HuggingFace API token for private models | None |
| `HUGGING_FACE_HUB_TOKEN` | Alternative name for HF_TOKEN | None |
| `USE_TRANSFORMERS_FALLBACK` | Enable transformers as fallback | `0` (disabled) |
| `HF_HOME` | Custom HuggingFace cache directory | `~/.cache/huggingface/` |
| `HUGGINGFACE_HUB_CACHE` | Alternative cache directory variable | `~/.cache/huggingface/hub/` |

---

## API Reference

### Main Function

```python
from the_chunker.chunking.tokenizer import count_tokens

count_tokens(
    text: str,           # Text to count tokens for
    model_name: str,     # Model name (e.g., "text-embedding-3-small")
    debug_level: str = "NONE"  # "NONE" or "VERBOSE"
) -> int  # Token count
```

**Examples:**
```python
# OpenAI model
count = count_tokens("Hello world", "text-embedding-3-small")

# HuggingFace model
count = count_tokens("Hello world", "Qwen/Qwen3-Embedding-8B")

# With debug output
count = count_tokens("Hello world", "gpt-4", debug_level="VERBOSE")
```

### Advanced: Direct Tokenizer Access

```python
from the_chunker.chunking.tokenizer_fetcher import get_hf_tokenizer

# Get a tokenizer wrapper
tokenizer = get_hf_tokenizer(
    model_name="Qwen/Qwen3-Embedding-8B",
    token=None,  # Optional: HF token for private models
    use_transformers_fallback=False  # Optional: enable transformers
)

# Use it
tokens = tokenizer.count_tokens("Hello world", add_special_tokens=False)
token_ids = tokenizer.encode("Hello world", add_special_tokens=False)
```

---

## Caching Behavior

### Two-Level Cache System

**Level 1: Disk Cache (Persistent)**
- Location: `~/.cache/huggingface/hub/`
- What: Downloaded tokenizer files
- Lifetime: Permanent (until manually cleared)
- Benefit: No re-download after restart

**Level 2: Memory Cache (Per Session)**
- Location: In-memory dictionary (`_tokenizer_cache`)
- What: Loaded tokenizer objects
- Lifetime: Current Python session
- Benefit: No file I/O for repeated use

**Cache clearing:**
```bash
# Clear all HuggingFace cache
rm -rf ~/.cache/huggingface/

# Or use the official tool
huggingface-cli delete-cache
```

---

## Troubleshooting

### Issue: "Model 'X' not found on HuggingFace Hub"

**Cause**: Model doesn't exist or name is misspelled

**Solutions:**
1. Check model exists: https://huggingface.co/models
2. Verify model name spelling
3. If testing, use a known model like `text-embedding-3-small`
4. Continue with tiktoken fallback (automatic)

### Issue: "Authentication required for model 'X'"

**Cause**: Model is private or gated

**Solution:**
```bash
export HF_TOKEN=your_token_here
# Get token from: https://huggingface.co/settings/tokens
```

### Issue: "Tokenizer not supported"

**Cause**: Unusual tokenizer not supported by lightweight libraries

**Solutions:**
1. **Recommended**: Use tiktoken fallback (automatic)
2. **Alternative**: Enable transformers fallback:
   ```bash
   pip install -e ".[transformers]"
   export USE_TRANSFORMERS_FALLBACK=1
   ```

### Issue: Slow first load

**Cause**: Downloading tokenizer files for the first time

**Expected Behavior**:
- First use: 2-10 seconds (downloads files)
- Subsequent uses: <1 second (uses cache)

**Not an issue** - this is normal behavior

---

## Performance Comparison

| Aspect | Lightweight (Default) | Transformers (Opt-in) |
|--------|----------------------|----------------------|
| Install size | ~40MB | ~4GB |
| Install time | <1 min | 5-10 min |
| First load | 1-3 sec | 10-30 sec |
| Memory usage | ~50MB | ~500MB+ |
| Token counting speed | ⚡ Same | ⚡ Same |
| Model support | 95% of models | 99% of models |

---

## Best Practices

### ✅ Recommended

1. **Use default lightweight mode** for most use cases
2. **Set HF_TOKEN** if working with private models
3. **Accept tiktoken fallback** for RAG chunking (approximate counts are fine)
4. **Let caching work** - don't clear cache unless needed
5. **Use known models** in production (validate before deploying)

### ❌ Not Recommended

1. **Don't enable transformers fallback** unless absolutely needed
2. **Don't clear cache** after every run
3. **Don't worry about** small token count differences for RAG
4. **Don't use placeholder names** in production (validate models exist)

---

## Migration from Old System

If migrating from the old transformers-based system, see [TOKENIZER_MIGRATION.md](./TOKENIZER_MIGRATION.md).

**Summary**: No code changes needed! The public API (`count_tokens()`) remains the same.

---

## Related Documentation

- [TOKENIZER_MIGRATION.md](./TOKENIZER_MIGRATION.md) - Migration guide from old system
- [README.md](./README.md) - Main project documentation
- [chunking-logic.md](./src/the_chunker/chunking/chunking-logic.md) - How chunking works

---

## Questions?

For issues or questions:
- Open an issue: https://github.com/QuarkCharmS/the_chunker/issues
- Check examples in [README.md](./README.md)
