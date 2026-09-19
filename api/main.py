"""
api/main.py

Platform API for the Shipping Document Verification system.

X / Platform responsibilities:
- expose the pipeline through HTTP
- store processed results
- provide data to the frontend
- expose the human review queue
- persist human review actions
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sdoc.core.pipeline import FolderSource, process_email, run

from api.storage import (
    get_all_results,
    get_email_summaries,
    get_result,
    get_review_queue,
    get_reviews,
    init_db,
    save_result,
    save_results,
    save_review,
    update_result_after_review,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BUNDLE_PATH = Path(
    os.getenv(
        "SDOC_BUNDLE_PATH",
        "sdoc-hackathon-bundle",
    )
)


def get_source() -> FolderSource:
    if not BUNDLE_PATH.exists():
        raise RuntimeError(
            f"Dataset folder not found: {BUNDLE_PATH}"
        )

    return FolderSource(BUNDLE_PATH)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Shipping Document Verification API",
    description=(
        "API for email classification, SI/BL comparison "
        "and human review."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    action: Literal["confirm", "correct"]
    field: Optional[str] = None
    corrected_value: Optional[str] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "shipping-document-verification",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Process entire inbox
# ---------------------------------------------------------------------------

@app.post("/process")
def process_inbox():
    """
    Run the team's real pipeline over the complete inbox.

    Results are persisted so the frontend can retrieve them through
    /emails and /emails/{id}.
    """

    try:
        source = get_source()

        results = run(source)

        save_results(results)

        review_count = sum(
            1
            for result in results.values()
            if result.needs_review
        )

        mismatch_count = sum(
            1
            for result in results.values()
            if result.has_defect
        )

        return {
            "message": "Inbox processed successfully",
            "processed": len(results),
            "needs_review": review_count,
            "mismatches": mismatch_count,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Process one existing dataset email
# ---------------------------------------------------------------------------

@app.post("/process/{email_id}")
def process_one_email(email_id: str):
    """
    Reprocess one email from the supplied dataset.
    Useful for retry handling.
    """

    try:
        source = get_source()

        email = next(
            (
                item
                for item in source.emails()
                if item.get("email_id") == email_id
            ),
            None,
        )

        if email is None:
            raise HTTPException(
                status_code=404,
                detail=f"Email {email_id} not found",
            )

        result = process_email(email, source)

        payload = result.to_dict()

        save_result(email_id, payload)

        return payload

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@app.get("/emails")
def list_emails():
    """
    Return lightweight email summaries for the frontend inbox.
    """

    emails = get_email_summaries()

    return {
        "count": len(emails),
        "emails": emails,
    }


# ---------------------------------------------------------------------------
# Individual report
# ---------------------------------------------------------------------------

@app.get("/emails/{email_id}")
def get_email(email_id: str):
    """
    Return the complete EmailResult.to_dict() representation.
    """

    result = get_result(email_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{email_id} has not been processed. "
                "Run POST /process first."
            ),
        )

    return result


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@app.get("/review-queue")
def review_queue():
    """
    Return all cases requiring human review.
    """

    queue = get_review_queue()

    return {
        "count": len(queue),
        "items": queue,
    }


# ---------------------------------------------------------------------------
# Human review
# ---------------------------------------------------------------------------

@app.post("/review/{email_id}")
def review_email(
    email_id: str,
    review: ReviewRequest,
):
    """
    Persist a human decision and update the stored report.

    Example confirmation:

        {
            "action": "confirm"
        }

    Example correction:

        {
            "action": "correct",
            "field": "port_of_loading",
            "corrected_value": "PORT KLANG"
        }
    """

    existing = get_result(email_id)

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Email {email_id} not found",
        )

    if review.action == "correct":
        if not review.field:
            raise HTTPException(
                status_code=400,
                detail="field is required for a correction",
            )

        if review.corrected_value is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "corrected_value is required "
                    "for a correction"
                ),
            )

    review_id = save_review(
        email_id=email_id,
        action=review.action,
        field=review.field,
        corrected_value=review.corrected_value,
    )

    try:
        updated = update_result_after_review(
            email_id=email_id,
            action=review.action,
            field=review.field,
            corrected_value=review.corrected_value,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "message": "Review saved",
        "review_id": review_id,
        "result": updated,
    }


# ---------------------------------------------------------------------------
# Review history - useful for demo/debugging
# ---------------------------------------------------------------------------

@app.get("/reviews/{email_id}")
def review_history(email_id: str):
    if get_result(email_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Email {email_id} not found",
        )

    reviews = get_reviews(email_id)

    return {
        "email_id": email_id,
        "count": len(reviews),
        "reviews": reviews,
    }


# ---------------------------------------------------------------------------
# Debug/status endpoint
# ---------------------------------------------------------------------------

@app.get("/stats")
def stats():
    results = get_all_results()

    return {
        "processed": len(results),
        "ok": sum(
            r.get("status") == "OK"
            for r in results
        ),
        "mismatch": sum(
            r.get("status") == "MISMATCH"
            for r in results
        ),
        "needs_review": sum(
            r.get("status") == "NEEDS_REVIEW"
            for r in results
        ),
    }