# The runner of the platform pipelines (Gitea Actions, host mode): the steps
# run in this container, which has what service and frontend builds need: a
# JDK, Node, Git, Python, the ECR helper and crane for daemonless OCI images.
ARG ACT_RUNNER_VERSION=0.6.1

FROM gitea/act_runner:${ACT_RUNNER_VERSION} AS act-runner

FROM --platform=$BUILDPLATFORM golang:1.25 AS ecr-login
ARG TARGETOS TARGETARCH
ARG ECR_LOGIN_VERSION=v0.12.0
RUN export CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    && go install github.com/awslabs/amazon-ecr-credential-helper/ecr-login/cli/docker-credential-ecr-login@${ECR_LOGIN_VERSION} \
    && go install github.com/google/go-containerregistry/cmd/crane@v0.20.3 \
    && mkdir /out \
    && cp "$(find /go/bin -name docker-credential-ecr-login)" /out/ \
    && cp "$(find /go/bin -name crane)" /out/

FROM eclipse-temurin:21-jdk-noble
ARG TARGETARCH
ARG NODE_VERSION=22.14.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates python3 curl xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 runner \
    && case "$TARGETARCH" in amd64) node_arch=x64 ;; arm64) node_arch=arm64 ;; *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac \
    && mkdir -p /opt/node \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" \
      | tar -xJ --strip-components=1 -C /opt/node
ENV PATH="/opt/node/bin:${PATH}"
COPY --from=act-runner /usr/local/bin/act_runner /usr/local/bin/act_runner
COPY --from=ecr-login /out/docker-credential-ecr-login /usr/local/bin/docker-credential-ecr-login
COPY --from=ecr-login /out/crane /usr/local/bin/crane
COPY entrypoint.sh config.yaml /etc/act_runner/
USER 10001
ENTRYPOINT ["/etc/act_runner/entrypoint.sh"]
