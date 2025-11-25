# Handlers Guide

## Overview

`handlers.py` provides three handlers for uploading content to Qdrant RAG backend:
- **FileHandler**: Single files
- **RepoHandler**: Git repositories
- **ArchiveHandler**: Zip/tar archives

## Architecture

```
FileHandler (atomic unit)
    ↑ used by
RepoHandler (clones repos, processes files)
    ↑ used by
ArchiveHandler (extracts archives, delegates to RepoHandler)
```

## Usage

```bash
# Single file
python handlers.py file <path> <code|text> <collection_name>

# Git repository
python handlers.py repo <git_url> <collection_name>

# Archive (.zip, .tar, .tar.gz, etc)
python handlers.py archive <path> <collection_name>
```

## How It Works

**FileHandler**:
1. Takes file path, type (code/text), and collection name
2. Chunks file based on type:
   - Code → Qwen model (3072 dims) via DeepInfra
   - Text → Cohere model (1024 dims)
3. Uploads to Qdrant

**RepoHandler**:
1. Clones git repo to temp directory
2. Walks all files recursively
3. Calls FileHandler for each file (assumes "code" type)
4. Cleans up temp directory

**ArchiveHandler**:
1. Extracts archive to temp directory
2. Uses RepoHandler's file processing logic
3. Cleans up temp directory

## Current State

- **No filtering**: Processes ALL files found
- **TODO markers** indicate where filtering logic will be added later
- RepoHandler assumes all files are "code" type

## Future Work

- File type detection (binary, text, code)
- Filtering module (skip node_modules, binaries, .git, etc.)
- Error handling improvements
- Move API keys to environment variables
