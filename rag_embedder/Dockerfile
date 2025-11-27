# Stage 1: Builder - Install the_chunker and all dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install the_chunker package
# NOTE: Build from parent directory: docker build -f rag_embedder/Dockerfile -t rag-embedder .
COPY the_chunker ./the_chunker

# Install the_chunker with lightweight dependencies (no transformers/torch)
RUN pip install --no-cache-dir ./the_chunker

# Copy and install rag_embedder requirements
COPY rag_embedder/requirements.txt ./rag_embedder_requirements.txt
RUN pip install --no-cache-dir -r ./rag_embedder_requirements.txt

# Stage 2: Runtime - Lightweight image with only installed packages and app code
FROM python:3.12-slim

WORKDIR /app

# Install runtime system dependencies (git for repo cloning, openssh for private repos)
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create .ssh directory for SSH keys (if needed for private repos)
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# Copy all installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application code
COPY rag_embedder/app ./app

# Set Python path
ENV PYTHONPATH=/app

# Set entrypoint to cli.py for command execution
# This allows: docker run rag-embedder collections create my_collection --vector-size 1536 --embedding-model text-embedding-3-small
ENTRYPOINT ["python", "-m", "app.cli"]

# Default command shows help
CMD ["--help"]
