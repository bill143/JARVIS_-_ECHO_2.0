# ECHO proxy — hardened multi-stage, non-root, pinned.
# ---- builder ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
# Install into an isolated prefix we can copy into the final stage.
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# ---- runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=4000

# Non-root user.
RUN groupadd --gid 10001 echo && \
    useradd --uid 10001 --gid echo --create-home --shell /usr/sbin/nologin echo

# curl for the container healthcheck only.
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY config.yaml healthcheck.py validate_config.py ./

USER echo

EXPOSE 4000

# Validate the registry at build/boot time, then start the proxy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:4000/health/liveliness || exit 1

CMD ["sh", "-c", "python validate_config.py && litellm --config config.yaml --port ${PORT} --host 0.0.0.0"]
