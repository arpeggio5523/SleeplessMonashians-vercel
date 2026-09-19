FROM python:3.11-slim

WORKDIR /app

# poppler-utils gives us pdftotext for faster PDF extraction;
# pdfplumber (in requirements.txt) is the fallback if this isn't available.
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects $PORT at runtime; default to 8080 for local testing.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}
