FROM ghcr.io/astral-sh/uv:debian-slim
WORKDIR /app

# Install system CA certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --locked --compile-bytecode
COPY . .

EXPOSE 8080
CMD ["uv","run","uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8080"]