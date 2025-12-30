# -----------------------------
# Base image
# -----------------------------
FROM registry.docker.ir/python:3.12-slim

# -----------------------------
# Metadata
# -----------------------------
LABEL maintainer="you@example.com"
LABEL description="TLS bootstrap container with OpenSSL and Kubernetes Python client"

# -----------------------------
# Install OpenSSL and dependencies
# -----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Install Python dependencies
# -----------------------------
RUN pip install --no-cache-dir kubernetes

# -----------------------------
# Create working directory
# -----------------------------
WORKDIR /work

# -----------------------------
# Copy your Python bootstrap script
# -----------------------------
COPY app.py app.py
# If you are using csr.conf from ConfigMap mount, no need to copy it here

# -----------------------------
# Command to run
# -----------------------------
CMD ["python", "app.py"]
