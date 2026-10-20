# Multi-stage build of the portal, so the only requirement is Docker.
# See https://backstage.io/docs/deployment/docker#multi-stage-build
#
# Build it with the engineering standards as an extra context:
#   docker build --build-context standards=../standards -t portal .

# Stage 1: the package.json files, to cache the dependency install.
FROM node:24-trixie-slim AS packages
WORKDIR /app
COPY backstage.json package.json yarn.lock .yarnrc.yml ./
COPY .yarn ./.yarn
COPY packages packages
COPY plugins plugins
RUN find packages plugins \! -name "package.json" -mindepth 2 -maxdepth 2 -exec rm -rf {} \+

# Stage 2: install dependencies and build the backend bundle and the app.
FROM node:24-trixie-slim AS build
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends python3 g++ build-essential libsqlite3-dev
ENV PYTHON=/usr/bin/python3
USER node
WORKDIR /app
COPY --from=packages --chown=node:node /app .
RUN --mount=type=cache,target=/home/node/.cache/yarn,sharing=locked,uid=1000,gid=1000 \
    yarn install --immutable
COPY --chown=node:node . .
RUN yarn tsc && yarn --cwd packages/backend build
RUN mkdir packages/backend/dist/skeleton packages/backend/dist/bundle \
    && tar xzf packages/backend/dist/skeleton.tar.gz -C packages/backend/dist/skeleton \
    && tar xzf packages/backend/dist/bundle.tar.gz -C packages/backend/dist/bundle

# Stage 3: the engineering standards as a TechDocs site.
FROM python:3.13-slim AS techdocs
WORKDIR /standards
COPY --from=standards requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=standards . .
RUN mkdocs build --quiet --site-dir /site \
    && python3 -c "import json,time; p='/site/techdocs_metadata.json'; m=json.load(open(p)); m['build_timestamp']=int(time.time()*1000); json.dump(m,open(p,'w'))"

# Stage 4: the runtime image.
FROM node:24-trixie-slim
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends python3 g++ build-essential libsqlite3-dev
ENV PYTHON=/usr/bin/python3
USER node
WORKDIR /app
COPY --from=build --chown=node:node /app/.yarn ./.yarn
COPY --from=build --chown=node:node /app/.yarnrc.yml /app/backstage.json ./
COPY --from=build --chown=node:node /app/yarn.lock /app/package.json /app/packages/backend/dist/skeleton/ ./
ENV NODE_ENV=production
RUN --mount=type=cache,target=/home/node/.cache/yarn,sharing=locked,uid=1000,gid=1000 \
    yarn workspaces focus --all --production && rm -rf "$(yarn cache clean)"
COPY --from=build --chown=node:node /app/packages/backend/dist/bundle/ ./
COPY --chown=node:node app-config.yaml ./
COPY --chown=node:node catalog ./catalog
COPY --from=standards --chown=node:node docs ./standards/docs
COPY --from=standards --chown=node:node catalog-info.yaml ./standards/
COPY --from=techdocs --chown=node:node /site ./techdocs/default/component/engineering-standards
EXPOSE 7007
CMD ["node", "packages/backend", "--config", "app-config.yaml"]
