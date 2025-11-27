# Tokenizer Migration Guide

This document explains the new lightweight tokenizer system and how to migrate from the old `transformers`-based approach.

## What Changed?

### Before (Heavy Dependencies)

The old system used `transformers` and `torch` for all HuggingFace models:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokens = len(tokenizer.encode(text, add_special_tokens=False))
```

**Issues:**
- Heavy dependencies (~4GB for torch + transformers)
- Slow installation and startup time
- Downloaded entire model configs and unnecessary files

### After (Lightweight System)

The new system uses minimal dependencies:

```python
from the_chunker.chunking.tokenizer_fetcher import get_hf_tokenizer

tokenizer = get_hf_tokenizer(model_name)
tokens = tokenizer.count_tokens(text, add_special_tokens=False)
```

**Benefits:**
- Lightweight dependencies (`huggingface_hub`, `tokenizers`, `sentencepiece`)
- Fast installation and startup
- Downloads only tokenizer files (not model weights)
- Local caching in `~/.cache/the_chunker/`
- Optional fallback to `transformers` if needed

## New Dependencies

### Required (Lightweight)

```
tiktoken==0.12.0          # For OpenAI models
huggingface_hub>=0.20.0   # For downloading tokenizer files
tokenizers>=0.15.0        # For BPE/WordPiece tokenizers
sentencepiece>=0.1.99     # For SentencePiece tokenizers (LLaMA, T5, etc.)
```

### Optional (Heavy - only if needed)

```
torch
transformers==4.51.0
```

## Installation Options

### Standard Installation (Lightweight)

```bash
pip install -e .
```

This installs only the lightweight dependencies. Works for 95% of use cases.

### With Transformers Fallback (Heavy)

```bash
pip install -e ".[transformers]"
# or
pip install -e ".[all]"
```

This includes `torch` and `transformers` as optional dependencies.

## Migration Steps

### 1. Update Dependencies

If you're using `requirements.txt`:

```bash
pip install -r requirements.txt
```

If you're using `pyproject.toml`:

```bash
pip install -e .
```

### 2. Update Your Code (If Needed)

**Good news:** The public API in `tokenizer.py` hasn't changed!

```python
# This still works exactly the same
from the_chunker.chunking.tokenizer import count_tokens

count = count_tokens("Hello world", "bert-base-uncased")
```

### 3. Set Environment Variables (Optional)

For private models:

```bash
export HF_TOKEN=your_huggingface_token
```

To enable transformers fallback:

```bash
export USE_TRANSFORMERS_FALLBACK=1
```

## Cache Location

Tokenizer files are cached automatically by `huggingface_hub` at:

```
~/.cache/huggingface/hub/
```

This is the standard HuggingFace cache location shared with all HuggingFace tools.

### Clearing Cache

To clear the tokenizer cache:

```bash
# Clear all HuggingFace cache
rm -rf ~/.cache/huggingface/

# Or use huggingface-cli
huggingface-cli delete-cache
```

To use a custom cache directory:

```bash
export HF_HOME=/path/to/custom/cache
# or
export HUGGINGFACE_HUB_CACHE=/path/to/custom/cache
```

## Supported Tokenizer Types

### OpenAI Models (via tiktoken)

- `gpt-4`, `gpt-4o`, `gpt-3.5-turbo`
- `text-embedding-3-small`, `text-embedding-3-large`
- `o1`, `o3`, `o4-mini`

### HuggingFace Models

#### BPE/WordPiece (via tokenizers library)

- BERT: `bert-base-uncased`, `roberta-base`
- GPT: `gpt2`, `distilgpt2`
- Most models with `tokenizer.json`

#### SentencePiece (via sentencepiece library)

- LLaMA: `meta-llama/Llama-2-7b-hf`, `meta-llama/Llama-3-8B`
- Qwen: `Qwen/Qwen3-Embedding-8B`
- T5: `t5-base`, `t5-large`
- XLNet: `xlnet-base-cased`

## Fallback Behavior

If the lightweight tokenizer loading fails, you can enable transformers fallback:

```bash
export USE_TRANSFORMERS_FALLBACK=1
```

This will:
1. Try lightweight loading first
2. If that fails, fall back to `transformers.AutoTokenizer`
3. Log a warning when fallback is used

## Troubleshooting

### Error: "huggingface_hub is required"

```bash
pip install huggingface_hub
```

### Error: "sentencepiece is required"

```bash
pip install sentencepiece
```

### Error: "tokenizers is required"

```bash
pip install tokenizers
```

### Model Not Found (404)

Check that the model exists on HuggingFace Hub:
https://huggingface.co/models

### Authentication Required (401)

Set your HuggingFace token:

```bash
export HF_TOKEN=your_token_here
```

### Access Forbidden (403)

The model is private. Set your HuggingFace token:

```bash
export HF_TOKEN=your_token_here
```

### Custom Tokenizer with trust_remote_code

If you need `trust_remote_code=True`, enable transformers fallback:

```bash
export USE_TRANSFORMERS_FALLBACK=1
pip install -e ".[transformers]"
```

## Performance Comparison

| Metric | Old (transformers) | New (lightweight) |
|--------|-------------------|-------------------|
| Install size | ~4GB | ~50MB |
| Install time | 5-10 min | 30 sec |
| First load time | 10-30 sec | 1-3 sec |
| Memory usage | 500MB+ | 50MB |
| Token counting speed | Same | Same |

## Breaking Changes

None! The public API remains the same. The changes are internal.

However, if you were directly importing from `transformers` in your code, you'll need to either:

1. Install the transformers extra: `pip install -e ".[transformers]"`
2. Or update your code to use the new lightweight system

## Questions?

For issues or questions, please open an issue at:
https://github.com/QuarkCharmS/the_chunker/issues
