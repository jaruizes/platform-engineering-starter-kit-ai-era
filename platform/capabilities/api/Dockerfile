# The platform API. Build it with the code Golden Paths and the capability
# schema it serves (deploy/install.sh does this):
#   docker build \
#     --build-context golden-paths=../golden-paths \
#     --build-context schema=../schema \
#     -t platform-starter-kit/platform-api:dev .
ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}
# git pushes the first commit of each new repository, keeping executable bits.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 platform
WORKDIR /app
COPY pyproject.toml ./
COPY platform_api ./platform_api
RUN pip install --no-cache-dir .
COPY --from=golden-paths . /app/golden-paths
COPY --from=schema capability-definition.schema.json /app/schema/capability-definition.schema.json
ENV GOLDEN_PATHS_DIR=/app/golden-paths \
    CAPABILITY_SCHEMA=/app/schema/capability-definition.schema.json
USER 10001
CMD ["platform-api"]
