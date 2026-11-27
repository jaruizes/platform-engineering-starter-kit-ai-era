ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}
WORKDIR /app
COPY pyproject.toml ./
COPY platform_mcp ./platform_mcp
RUN pip install --no-cache-dir . && useradd --uid 10001 platform
USER 10001
CMD ["platform-mcp"]
