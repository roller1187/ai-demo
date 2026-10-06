FROM registry.access.redhat.com/ubi9/openjdk-17:latest AS builder
USER root
WORKDIR /build
COPY pom.xml .
COPY src src
RUN chown -R 185:0 /build && chmod -R g=u /build
USER 185
RUN mvn clean package -DskipTests

FROM registry.access.redhat.com/ubi9/openjdk-17-runtime:latest
WORKDIR /deployments
COPY --from=builder /build/target/quarkus-app /deployments/
EXPOSE 8080
ENV JAVA_APP_JAR="/deployments/quarkus-run.jar"
