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

ENV PORT=8080

EXPOSE 8080


CMD exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port ${PORT}