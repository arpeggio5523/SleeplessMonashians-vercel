const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "https://sdoc-api-856612571283.asia-southeast1.run.app"
).replace(/\/+$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Request failed (${response.status})`
    );
  }

  return data;
}

export async function getAllEmails() {
  const data = await request("/emails");
  return data.emails;
}

export async function getEmail(emailId) {
  return request(`/emails/${encodeURIComponent(emailId)}`);
}

export async function getReviewQueue() {
  const data = await request("/review-queue");
  return data.items;
}

export async function submitReview(emailId, decision) {
  const payload = {
    action: decision.action,
  };

  if (decision.action === "correct") {
    payload.field = decision.field;
    payload.corrected_value = decision.value;
  }

  return request(`/review/${encodeURIComponent(emailId)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}