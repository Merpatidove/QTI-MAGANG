FROM rust:1-bookworm AS builder

WORKDIR /app

COPY Cargo.toml ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true
RUN rm -rf src

COPY src/ src/
RUN touch src/main.rs && cargo build --release

# Bake the embedding model into the image at build time (the build machine has
# internet). The runtime cluster is air-gapped, so the model must be present.
ENV EMBED_CACHE_DIR=/opt/fastembed
RUN /app/target/release/api-gateway --download-only

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /app/target/release/api-gateway /usr/local/bin/api-gateway
COPY --from=builder /opt/fastembed /opt/fastembed

ENV EMBED_CACHE_DIR=/opt/fastembed

USER appuser

EXPOSE 8080

ENTRYPOINT ["api-gateway"]
