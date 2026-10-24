let csrfToken = "";
export function setSessionToken(value) {
  csrfToken = value || "";
}

export async function api(path, { method = "GET", body, signal, responseType = "json" } = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      signal,
      credentials: "same-origin",
      headers: {
        ...(body && !(body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...(method !== "GET" && csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body:
        body instanceof FormData
          ? body
          : body
            ? JSON.stringify(body)
            : undefined,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Cannot reach PolicyLens. Check that the Python server is running.",
    );
  }
  let data;
  if (response.ok && responseType === "blob") {
    if (response.headers.get("content-type")?.split(";")[0] !== "application/zip")
      throw new Error("The server did not return an evidence archive.");
    return response.blob();
  }
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The Python API did not return a valid response. This deployment needs the PolicyLens backend connected at /api.",
    );
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("policylens-session-expired"));
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item) => `${item.loc.slice(1).join(" → ")}: ${item.msg}`)
              .join("; ")
          : detail?.message || "The request failed. Please try again.";
    const error = new Error(message);
    error.status = response.status;
    error.details = detail;
    throw error;
  }
  return data;
}
