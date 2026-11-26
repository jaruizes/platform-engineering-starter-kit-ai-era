# Optional local Docker build; Gitea Actions publishes multi-architecture images
# using the daemonless scripts/build-image.sh instead.
FROM python:3.12-slim-bookworm
WORKDIR /opt/app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY pyproject.toml operations.json ./
COPY rest_mcp_adapter/ ./rest_mcp_adapter/
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app
USER 10001
EXPOSE 8080
CMD ["python", "-m", "rest_mcp_adapter.server"]
