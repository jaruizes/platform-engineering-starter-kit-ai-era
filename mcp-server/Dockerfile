ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}
WORKDIR /app
COPY pyproject.toml ./
COPY platform_mcp ./platform_mcp
RUN pip install --no-cache-dir . && useradd --uid 10001 platform
USER 10001
# The same image runs the MCP server (platform-mcp) or the console (platform-console).
CMD ["platform-mcp"]
