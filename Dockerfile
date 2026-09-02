FROM ghcr.io/astral-sh/uv:debian-slim

# Set working directory
WORKDIR /app

# 1. Bring in the official fast 'uv' binary (faster and cleaner than pip installing it!)
COPY pyproject.toml uv.lock /app/

RUN uv sync --locked


# 3. Limit parallel downloads
ENV UV_CONCURRENT_DOWNLOADS=4

# 5. Copy the rest of your application code
COPY . /app/

# 6. Make entrypoint executable if you are using one
# (Comment this out if you don't actually have a docker-entrypoint.sh file in your folder)
# RUN chmod +x /app/docker-entrypoint.sh && sed -i 's/\r$//' /app/docker-entrypoint.sh

# 7. Final Sync (Install the project itself)
RUN uv sync --no-dev

# 9. Expose the port
EXPOSE 8000

# 10. Run Uvicorn directly (since .venv/bin is in the PATH, it will be found instantly!)
CMD ["uv", "run", "fastapi", "dev", "--host", "0.0.0.0", "--port", "8000"]
