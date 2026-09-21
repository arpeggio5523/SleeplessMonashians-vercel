FROM python:3.11-slim

WORKDIR /app


# --------------------------------------------------
# System dependencies
# --------------------------------------------------

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*


# --------------------------------------------------
# Python dependencies
# --------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


# --------------------------------------------------
# Application
# --------------------------------------------------

COPY api ./api
COPY sdoc ./sdoc

# Hackathon dataset used by FolderSource
COPY sdoc-hackathon-bundle ./sdoc-hackathon-bundle

# Cached Gemini classifications, so the deployed service reproduces our
# numbers with no API key and cannot be broken by a rate limit.
COPY .cache/llm ./.cache/llm


# --------------------------------------------------
# Runtime
# --------------------------------------------------

RUN mkdir -p /app/data

ENV SDOC_BUNDLE_PATH=/app/sdoc-hackathon-bundle
ENV SDOC_DB_PATH=/app/data/sdoc.db

# Flash-Lite: ~500 free requests/day vs ~20 for the full Flash models, and
# indistinguishable on this task. The committed .cache/llm means a normal run
# makes no calls at all.
ENV SDOC_GEMINI_MODEL=gemini-3.5-flash-lite
ENV SDOC_LLM_RPM=15

ENV PORT=8080

EXPOSE 8080


CMD exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port ${PORT}