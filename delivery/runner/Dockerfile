# The runner of the platform pipelines (Gitea Actions, host mode): the steps
# run in this container, which has what a service build needs: a JDK, Git and
# the ECR credential helper Jib uses on AWS. No Docker: Jib builds images
# without it.
ARG ACT_RUNNER_VERSION=0.6.1

FROM gitea/act_runner:${ACT_RUNNER_VERSION} AS act-runner

FROM --platform=$BUILDPLATFORM golang:1.25 AS ecr-login
ARG TARGETOS TARGETARCH
ARG ECR_LOGIN_VERSION=v0.12.0
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go install github.com/awslabs/amazon-ecr-credential-helper/ecr-login/cli/docker-credential-ecr-login@${ECR_LOGIN_VERSION} \
    && mkdir /out && cp "$(find /go/bin -name docker-credential-ecr-login)" /out/

FROM eclipse-temurin:21-jdk-noble
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 runner
COPY --from=act-runner /usr/local/bin/act_runner /usr/local/bin/act_runner
COPY --from=ecr-login /out/docker-credential-ecr-login /usr/local/bin/docker-credential-ecr-login
COPY entrypoint.sh config.yaml /etc/act_runner/
USER 10001
ENTRYPOINT ["/etc/act_runner/entrypoint.sh"]
