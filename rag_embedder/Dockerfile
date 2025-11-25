# Builder stage: install the_chunker
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy and install the_chunker package
# NOTE: Build from parent directory: docker build -f rag_in_aws/Dockerfile -t rag-cli .
COPY the_chunker ./the_chunker
RUN pip install --no-cache-dir ./the_chunker

# Final stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create .ssh directory for SSH keys (if needed)
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the installed the_chunker package from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages/the_chunker /usr/local/lib/python3.12/site-packages/the_chunker

# Copy application code
COPY app/ ./app/

# Make CLI executable
RUN chmod +x app/cli.py

# Set Python path
ENV PYTHONPATH=/app

# Set entrypoint to run the CLI
ENTRYPOINT ["python", "-m", "app.cli"]

# Default command shows help
CMD ["--help"]
