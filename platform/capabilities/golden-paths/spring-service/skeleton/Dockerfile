# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 mvn -B -q dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 mvn -B -q package -DskipTests

# OpenTelemetry Java agent (technology policy: OpenTelemetry). Configured only
# through OTEL_* variables; without an endpoint it exports nothing.
FROM curlimages/curl:8.11.1 AS otel
ARG OTEL_AGENT_VERSION=2.11.0
RUN curl -sSfL -o /tmp/opentelemetry-javaagent.jar \
    "https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v${OTEL_AGENT_VERSION}/opentelemetry-javaagent.jar"

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --system --uid 10001 appuser
COPY --from=otel /tmp/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar
COPY --from=build /build/target/*.jar /app/app.jar
ENV JAVA_TOOL_OPTIONS="-javaagent:/app/opentelemetry-javaagent.jar" \
    OTEL_SERVICE_NAME=${{ values.name }}
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
