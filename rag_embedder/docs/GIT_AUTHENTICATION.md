# Git Authentication Guide

Simple guide for cloning Git repositories (public and private) with the RAG system.

---

## TL;DR - Quick Start

### Public Repositories
```python
handler.handle(git_url="https://github.com/user/repo.git", ...)
# That's it! No auth needed.
```

### Private HTTPS Repositories
```python
handler.handle(
    git_url="https://github.com/user/private-repo.git",
    git_token="ghp_yourGitHubToken",  # ← Just add token
    ...
)
```

### Private SSH Repositories
```bash
# Mount SSH key to standard location:
docker run -v ~/.ssh:/root/.ssh:ro your-image

# Or locally: key should be at ~/.ssh/id_rsa or ~/.ssh/id_ed25519
```

```python
handler.handle(
    git_url="git@github.com:user/private-repo.git",  # ← SSH URL
    # SSH key auto-detected from ~/.ssh/ - nothing to configure!
    ...
)
```

---

## How It Works

### The system is smart:

**For Public Repos**: Just works, no configuration

**For HTTPS URLs** (`https://github.com/...`):
1. Tries to clone without authentication
2. If that fails and you provided `git_token`, uses it
3. If no token, tells you how to get one

**For SSH URLs** (`git@github.com:...`):
1. Auto-detects SSH keys from standard locations:
   - `~/.ssh/id_rsa`
   - `~/.ssh/id_ed25519`
   - `~/.ssh/id_ecdsa`
   - `/root/.ssh/*` (for containers)
2. Tries system SSH config first
3. Falls back to each detected key
4. Clear error if no keys found

### You don't configure SSH keys - they're auto-detected! 🎉

---

## For Private HTTPS Repositories

### Step 1: Generate a Personal Access Token

**GitHub**:
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scope: ✅ `repo`
4. Copy the token (starts with `ghp_`)

**GitLab**:
1. Go to https://gitlab.com/-/profile/personal_access_tokens
2. Create token
3. Select scope: ✅ `read_repository`

**Bitbucket**:
1. Go to https://bitbucket.org/account/settings/app-passwords/
2. Create app password
3. Select: ✅ `Repositories: Read`

### Step 2: Use It

```python
from handlers import RepoHandler

handler = RepoHandler()
handler.handle(
    git_url="https://github.com/user/private-repo.git",
    collection_name="my_collection",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_embedding_api_token",
    git_token="ghp_yourGitHubToken123456"  # ← Your token
)
```

### Step 3: Use Environment Variables (Better)

```bash
# Set environment variable
export GITHUB_TOKEN="ghp_yourToken123456"
```

```python
import os

handler.handle(
    git_url="https://github.com/user/private-repo.git",
    git_token=os.getenv("GITHUB_TOKEN"),  # ← From environment
    ...
)
```

---

## For Private SSH Repositories

### Step 1: Generate SSH Key (if you don't have one)

```bash
# Generate key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Press Enter to save to default location (~/.ssh/id_ed25519)
# Press Enter twice for no passphrase (or set one if you prefer)
```

### Step 2: Add Public Key to Git Provider

```bash
# Copy your public key
cat ~/.ssh/id_ed25519.pub
```

**GitHub**: Go to https://github.com/settings/keys → New SSH key → Paste

**GitLab**: Go to https://gitlab.com/-/profile/keys → Paste

**Bitbucket**: Go to https://bitbucket.org/account/settings/ssh-keys/ → Add key

### Step 3: Test Connection

```bash
ssh -T git@github.com
# Should see: "Hi username! You've successfully authenticated..."
```

### Step 4: Use It (No Configuration!)

```python
handler.handle(
    git_url="git@github.com:user/private-repo.git",  # SSH format
    # That's it! SSH key is auto-detected from ~/.ssh/
    ...
)
```

---

## Container Deployment

### Docker

Mount your SSH directory:

```bash
docker run -v ~/.ssh:/root/.ssh:ro your-rag-image
```

That's it! The system finds the keys automatically.

### Kubernetes

Create a secret with your SSH key:

```bash
kubectl create secret generic git-ssh-keys \
  --from-file=id_ed25519=~/.ssh/id_ed25519
```

Mount it in your pod:

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: rag-worker
    volumeMounts:
    - name: ssh-keys
      mountPath: /root/.ssh
      readOnly: true
  volumes:
  - name: ssh-keys
    secret:
      secretName: git-ssh-keys
      defaultMode: 0600
```

The system auto-detects mounted keys. No code changes needed!

### AWS ECS/Fargate

Store SSH key in AWS Secrets Manager, then mount as file in container. System auto-detects it.

---

## Usage Examples

### Example 1: Public Repo (HTTPS)
```python
from handlers import RepoHandler

handler = RepoHandler()
handler.handle(
    git_url="https://github.com/torvalds/linux.git",
    collection_name="linux_kernel",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_embedding_token"
)
```

### Example 2: Private Repo (HTTPS with Token)
```python
import os

handler = RepoHandler()
handler.handle(
    git_url="https://github.com/company/private-api.git",
    collection_name="company_api",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_embedding_token",
    git_token=os.getenv("GITHUB_TOKEN")  # From environment
)
```

### Example 3: Private Repo (SSH)
```python
# Ensure SSH key exists at ~/.ssh/id_ed25519 or ~/.ssh/id_rsa
# Add public key to GitHub settings

handler = RepoHandler()
handler.handle(
    git_url="git@github.com:company/private-api.git",
    collection_name="company_api",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_embedding_token"
    # No git_token needed for SSH!
)
```

### Example 4: Sync Private Repo (Updates Only)
```python
from qdrant_manager import QdrantManager

manager = QdrantManager()
stats = manager.sync_repo(
    git_url="git@github.com:company/codebase.git",
    collection_name="company_code",
    embedding_model="Qwen/Qwen3-Embedding-8B",
    api_token="your_embedding_token"
    # SSH key auto-detected!
)

print(f"Added: {stats['added']}, Updated: {stats['updated']}, Deleted: {stats['deleted']}")
```

---

## Troubleshooting

### "SSH authentication failed. No SSH keys found."

**Container**: Mount your SSH key
```bash
docker run -v ~/.ssh:/root/.ssh:ro your-image
```

**Local**: Generate SSH key
```bash
ssh-keygen -t ed25519
```

### "Repository appears to be private but no token provided"

**Solution**: Provide `git_token` parameter
```python
handler.handle(..., git_token="ghp_yourtoken")
```

### "Authentication with token failed"

Check:
- ✅ Token is valid (not expired)
- ✅ Token has `repo` scope (GitHub)
- ✅ You have access to the repository
- ✅ Token is for the correct platform (GitHub/GitLab/Bitbucket)

### "SSH authentication failed with all found keys"

Your public key isn't added to git provider:
```bash
# Test connection
ssh -T git@github.com

# If fails, add your public key
cat ~/.ssh/id_ed25519.pub
# Copy output and add to GitHub settings
```

---

## Security Best Practices

### 1. Use Environment Variables
```python
# ❌ BAD - Token in code
git_token = "ghp_123456"

# ✅ GOOD - Token from environment
git_token = os.getenv("GITHUB_TOKEN")
```

### 2. Mount SSH Keys Read-Only in Containers
```bash
# ✅ GOOD - read-only mount
-v ~/.ssh:/root/.ssh:ro

# ❌ BAD - writable mount
-v ~/.ssh:/root/.ssh
```

### 3. Protect SSH Private Keys
```bash
chmod 600 ~/.ssh/id_ed25519  # Owner read/write only
```

### 4. Use Minimal Token Permissions
- GitHub: Only `repo` (read) scope
- Don't grant write/admin unless needed

### 5. Rotate Tokens Regularly
- Regenerate every 90 days
- Delete old tokens after rotation

---

## Configuration in Test Files

In `tests/test_all_file_types.py`:

```python
# For public repos
GIT_TOKEN = None

# For private HTTPS repos
GIT_TOKEN = "ghp_yourtoken"  # Or os.getenv("GITHUB_TOKEN")

# For private SSH repos
# No configuration needed! Just ensure key is at ~/.ssh/id_rsa or ~/.ssh/id_ed25519
```

---

## Summary

| Repository Type | What You Need | Configuration |
|----------------|---------------|---------------|
| **Public** | Nothing | Just the URL |
| **Private HTTPS** | Personal Access Token | `git_token="ghp_..."` |
| **Private SSH** | SSH key in `~/.ssh/` | Nothing! Auto-detected |

**Key Points**:
- ✅ SSH keys are **always auto-detected** - no manual configuration
- ✅ HTTPS tries **public first**, then uses token if provided
- ✅ **Container-friendly** - just mount keys to standard locations
- ✅ **Clear errors** when credentials are needed

---

## Quick Reference

### RepoHandler
```python
handler = RepoHandler()
handler.handle(
    git_url="...",              # HTTPS or SSH
    collection_name="...",
    embedding_model="...",
    api_token="...",
    git_token="ghp_xxx"         # Optional: For private HTTPS only
)
```

### QdrantManager.sync_repo
```python
manager = QdrantManager()
stats = manager.sync_repo(
    git_url="...",              # HTTPS or SSH
    collection_name="...",
    embedding_model="...",
    api_token="...",
    git_token="ghp_xxx"         # Optional: For private HTTPS only
)
```

**Note**: No `git_ssh_key` parameter exists - SSH keys are always auto-detected! 🎉
