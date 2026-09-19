"""
FastAPI wrapper around the shipping-document verification pipeline.

Endpoints:
  GET  /health           - liveness check (Cloud Run pings this)
  POST /classify          - classify a single email (subject + body only, no files needed)
  POST /process            - full pipeline: classify + (if BL_COMPARISON) extract/compare attachments

Run locally:
  uvicorn app:app --reload --port 8000

Deploy:
  gcloud run deploy --source .
"""
import json
from typing import List, Optional

from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import processing

app = FastAPI(title="Shipping Document Verification API", version="0.1.0")

# Allow the future dashboard/UI (Phase 3) to call this from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class EmailIn(BaseModel):
    subject: Optional[str] = ""
    body: Optional[str] = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify")
def classify_email(email: EmailIn):
    """Classify an email with no attachments considered (quick triage)."""
    category = processing.classify(email.subject, email.body, has_attachments=False)
    return {"category": category}


@app.post("/process")
async def process_email(
    email: str = Form(..., description="JSON string: {\"subject\": ..., \"body\": ...}"),
    files: List[UploadFile] = File(default=[]),
):
    """
    Full pipeline for one email.

    Send as multipart/form-data:
      - email: JSON string with "subject" and "body"
      - files: 0, 1, or 2 attachment files. For a document-comparison request,
               upload the SI file first, then the BL file (order matters).
    """
    email_data = json.loads(email)
    subject = email_data.get("subject", "")
    body = email_data.get("body", "")

    attachments = []
    for f in files:
        content = await f.read()
        attachments.append({"filename": f.filename, "content": content})

    result = processing.process_email(subject, body, attachments)
    return result
