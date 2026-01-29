# Dafny Verification Service - Minimal Dockerfile
# 
# SECURITY: This image has NO secrets, NO credentials, NO database access.
# It is designed to run in network isolation with only verification capabilities.

FROM python:3.13-slim AS builder

WORKDIR /app

# Install Python dependencies
COPY verifier/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies for Dafny/.NET
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    unzip \
    libc6 \
    libgcc1 \
    libgssapi-krb5-2 \
    libicu-dev \
    libssl3 \
    libstdc++6 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Install .NET 8.0 runtime (not full SDK - smaller image)
RUN wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 8.0 --runtime dotnet --install-dir /usr/share/dotnet && \
    ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet && \
    rm /tmp/dotnet-install.sh

# Install Dafny as a .NET tool
# Note: This requires .NET SDK, so we install it temporarily
RUN wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet && \
    dotnet tool install --global dafny && \
    rm /tmp/dotnet-install.sh

# Install Z3 solver (version compatible with Dafny)
RUN mkdir -p /root/.dotnet/tools/z3/bin && \
    curl -sL https://github.com/Z3Prover/z3/releases/download/z3-4.12.1/z3-4.12.1-x64-glibc-2.35.zip -o /tmp/z3.zip && \
    unzip -q /tmp/z3.zip -d /tmp && \
    cp /tmp/z3-4.12.1-x64-glibc-2.35/bin/z3 /root/.dotnet/tools/z3/bin/z3-4.12.1 && \
    chmod +x /root/.dotnet/tools/z3/bin/z3-4.12.1 && \
    rm -rf /tmp/z3.zip /tmp/z3-4.12.1-x64-glibc-2.35

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy verifier application code ONLY
COPY verifier/ /app/verifier/

# Set PATH for Python packages, .NET tools, and Z3
ENV PATH=/root/.local/bin:/root/.dotnet/tools:/root/.dotnet/tools/z3/bin:$PATH

# SECURITY: No environment variables for credentials
# SECURITY: No volumes mounting secrets
# SECURITY: No database connection strings

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the verification service
# Using module syntax to ensure proper Python imports
CMD ["python", "-m", "uvicorn", "verifier.main:app", "--host", "0.0.0.0", "--port", "8001"]
