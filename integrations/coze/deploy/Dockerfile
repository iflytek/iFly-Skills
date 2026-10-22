ARG PYTHON_IMAGE=python:3.13-slim-bookworm
FROM caddy:2.10.2-alpine AS proxy
# The proxy listens on 8443; its executable needs no privileged-port file cap.
# Leaving that cap in place can make exec fail with cap_drop=ALL on Linux.
RUN setcap -r /usr/bin/caddy

FROM ${PYTHON_IMAGE} AS backend
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/iflytek/iFly-Skills" \
      org.opencontainers.image.revision="${SOURCE_REVISION}"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/integrations/coze
COPY integrations/coze/pyproject.toml integrations/coze/uv.lock ./
RUN python -m pip install --no-cache-dir uv==0.12.1 \
    && uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python \
    && uv cache clean
COPY integrations/coze/app ./app
COPY skills /app/skills
COPY LICENSE /app/LICENSE
USER 10001:10001
EXPOSE 8000
CMD ["/app/integrations/coze/.venv/bin/python", "-B", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers", "--timeout-graceful-shutdown", "30"]
