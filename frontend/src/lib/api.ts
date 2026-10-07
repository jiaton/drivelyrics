export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * fetch + JSON with the session cookie. A 401 means the session is gone (signed out on
 * another device, or never signed in): reload, and the app lands on the sign-in screen.
 */
export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(path, {
    credentials: "same-origin",
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...rest.headers } : rest.headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 401 && path !== "/api/auth/me") {
    window.location.assign("/");
    throw new ApiError(401, "signed out");
  }
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = String(body.detail[0].msg).replace(/^Value error, /, "");
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}
