# Guardian Gateway - Dockerfile
# Uses official Dafny release with bundled Z3

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libicu-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and install Dafny with bundled Z3
ENV DAFNY_VERSION=4.9.1
RUN wget -q https://github.com/dafny-lang/dafny/releases/download/v${DAFNY_VERSION}/dafny-${DAFNY_VERSION}-x64-ubuntu-20.04.zip \
    && unzip -q dafny-${DAFNY_VERSION}-x64-ubuntu-20.04.zip -d /opt \
    && rm dafny-${DAFNY_VERSION}-x64-ubuntu-20.04.zip \
    && chmod -R +x /opt/dafny

# Add Dafny to PATH
ENV PATH="/opt/dafny:${PATH}"

# Verify Dafny installation (this also verifies Z3 is working)
RUN dafny --version

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
