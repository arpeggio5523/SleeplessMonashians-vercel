# X — Platform / Backend Instructions

## What X Does

X turns the shipping-document pipeline into a **public backend API**.

The pipeline runs in a Docker container hosted on **Google Cloud Run**, allowing the frontend and other team members to access the processing system through HTTP instead of running Python locally.

Flow:

    Pipeline (sdoc/core)
           ↓
       FastAPI
           ↓
      Cloud Run
           ↓
    Public HTTPS URL
           ↓
       Frontend

---

## Hosted Backend

Base URL:

    https://sdoc-api-856612571283.asia-southeast1.run.app

All API endpoints are added after this URL.

For example:

    https://sdoc-api-856612571283.asia-southeast1.run.app/health

The API is publicly accessible, so no Google Cloud login is required.

---

## API Documentation

Interactive API documentation is available at:

    https://sdoc-api-856612571283.asia-southeast1.run.app/docs

Swagger can be used to view and test the available endpoints.

Click an endpoint → **Try it out** → **Execute**.

---

## Endpoints

### `GET /health`

Checks whether the Cloud Run backend is online.

Example:

    GET /health

Response:

    {
      "status": "ok",
      "service": "shipping-document-verification",
      "version": "1.0.0"
    }

---

### `POST /process`

Runs the shipping-document pipeline over the inbox and stores the results.

Example:

    POST /process

No request body is required.

After processing, the results become available through `/emails`.

---

### `GET /emails`

Returns the processed emails for the frontend inbox.

Example:

    GET /emails

Response structure:

    {
      "count": 520,
      "emails": [
        {
          "email_id": "email_001",
          "category": "BL_COMPARISON",
          "status": "MISMATCH",
          "needs_review": false
        }
      ]
    }

Use this endpoint for the **Inbox page**.

---

### `GET /emails/{email_id}`

Returns the complete processing result for one email.

Example:

    GET /emails/email_001

The response uses the pipeline's existing:

    EmailResult.to_dict()

format.

It contains information such as:

- classification
- processing status
- SI/BL comparisons
- mismatched fields
- source evidence
- review reason
- notes

Use this endpoint for the **Report page**.

---

### `GET /review-queue`

Returns emails that require human review.

Example:

    GET /review-queue

Possible reasons include:

    missing_attachment
    unreadable
    wrong_doc_type
    missing_value

Use this endpoint for the **Review Queue page**.

---

### `POST /review/{email_id}`

Submits a human decision for an escalated email.

To confirm the existing result:

    POST /review/email_001

Body:

    {
      "action": "confirm"
    }

To provide a correction:

    {
      "action": "correct",
      "field": "port_of_loading",
      "corrected_value": "PORT KLANG"
    }

The review is stored and the email result is updated.

---

### `POST /process/{email_id}`

Reprocesses one email.

Example:

    POST /process/email_001

This can be used as the **Retry** function when processing fails or an email needs to be processed again.

---

## Frontend Usage

The frontend should call the API using `fetch()`.

Example:

    const API_URL =
      "https://sdoc-api-856612571283.asia-southeast1.run.app";

    const response = await fetch(`${API_URL}/emails`);
    const data = await response.json();

Typical frontend flow:

    GET /emails
         ↓
    Inbox
         ↓
    Select email
         ↓
    GET /emails/{id}
         ↓
    Report

For human review:

    GET /review-queue
         ↓
    Select case
         ↓
    POST /review/{id}
         ↓
    Refresh report

---

## Running X Locally

From the project root:

    pip install -r requirements.txt

Then:

    uvicorn api.main:app --reload --port 8000

Open:

    http://localhost:8000/docs

---

## Deployment

X is deployed to **Google Cloud Run**.

Deployment is performed from the project root:

    gcloud run deploy sdoc-api --source . --region asia-southeast1 --allow-unauthenticated

Do not deploy from the old `service/` folder.

---

## Files Owned by X

    api/
    ├── main.py
    └── storage.py

    Dockerfile
    requirements.txt
    .dockerignore
    .env.example

`api/main.py` exposes the HTTP API.

`api/storage.py` handles storing processed results and human review actions.

`Dockerfile` packages the application for Cloud Run.

---

## Important

The API does **not** implement its own classification or SI/BL comparison logic.

It calls the existing:

    sdoc/core/

pipeline.

Therefore:

    I/P updates pipeline
            ↓
    X exposes updated result
            ↓
    U receives it through API

The API should continue returning `EmailResult.to_dict()` so the frontend and pipeline use the same data format.