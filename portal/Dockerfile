# Multi-stage build of the portal, so the only requirement is Docker.
# See https://backstage.io/docs/deployment/docker#multi-stage-build
#
# Build it with the engineering standards, the capabilities and the branding
# (branding/README.md) as extra contexts:
#   docker build --build-context standards=../standards \
#     --build-context capabilities=../capabilities \
#     --build-context branding=branding -t portal .
# The branding is the last layer, so changing it alone rebuilds in seconds.

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

# Stage 4: the documentation of each platform capability, as TechDocs sites.
FROM techdocs AS capability-docs
COPY --from=capabilities . /capabilities
RUN mkdir -p /capability-sites && for mk in /capabilities/*/mkdocs.yml; do \
      [ -f "$mk" ] || continue; \
      name="$(basename "$(dirname "$mk")")"; \
      (cd "$(dirname "$mk")" && mkdocs build --quiet --site-dir "/capability-sites/$name") || exit 1; \
      python3 -c "import json,sys,time; p=sys.argv[1]; m=json.load(open(p)); m['build_timestamp']=int(time.time()*1000); json.dump(m,open(p,'w'))" "/capability-sites/$name/techdocs_metadata.json"; \
    done

# Stage 5: the runtime image.
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
COPY --from=standards --chown=node:node catalog-info.yaml architectures.yaml ./standards/
COPY --from=techdocs --chown=node:node /site ./techdocs/default/component/engineering-standards
COPY --from=capabilities --chown=node:node schema ./capabilities/schema
COPY --from=capability-docs --chown=node:node /capability-sites ./techdocs/default/resource
# The branding goes last: its configuration is merged over app-config.yaml and
# its images are served by the portal under /branding.
COPY --from=branding --chown=node:node . ./branding/
RUN mkdir -p packages/app/dist/branding \
    && find branding -maxdepth 1 -type f ! -name '*.yaml' ! -name '*.md' -exec cp {} packages/app/dist/branding/ \;
EXPOSE 7007
CMD ["node", "packages/backend", "--config", "app-config.yaml", "--config", "branding/branding.yaml"]
