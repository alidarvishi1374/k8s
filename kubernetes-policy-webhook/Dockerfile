
# ------------------------
# Base image
# ------------------------
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application code
COPY app.py /app

# Create non-root user
RUN useradd -ms /bin/bash webhookuser \
 && chown -R webhookuser:webhookuser /app /usr/local/lib/python3.12/site-packages
USER webhookuser

# Expose webhook port
EXPOSE 8443

# Healthcheck (check HTTPS on localhost)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD curl --silent --fail --cacert /app/certs/ca.crt https://localhost:8443/health || exit 1

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8443", "--certfile=certs/tls.crt", "--keyfile=certs/tls.key", "app:app"]

