# Dockerfile for Cloud-to-IaC Analyzer with LocalStack Integration
# This sets up a complete environment with LocalStack S3 service

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cloud_iac_analyzer/ ./cloud_iac_analyzer/
COPY examples/ ./examples/

# Create output directory
RUN mkdir -p /app/output

# Set the CLI as the entrypoint
ENTRYPOINT ["python", "-m", "cloud_iac_analyzer.cli"]

# Default command (can be overridden)
CMD ["examples/cloud_resources.json", "examples/iac_resources.json", "output/report.json"]
