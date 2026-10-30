import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { clearCache, readCache, writeCache } from "../../../lib/cache";
import type { EmailStart, Me } from "../types";

export function useMe() {
  // Last known answer first (drawn at once), then the server's (see lib/cache).
  const [me, setMe] = useState<Me | null>(() => readCache<Me>("me"));
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Me>("/api/auth/me")
      .then((body) => {
        setMe(body);
        setError(null);
        writeCache("me", body);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  return { me, error, refresh };
}

export async function signOut() {
  await api("/api/auth/logout", { method: "POST" });
  clearCache();
  window.location.assign("/");
}

export async function devSignIn(email: string) {
  await api("/api/auth/dev-login", { method: "POST", json: { email } });
}

export function googleSignInUrl(next: string = "/") {
  return `/api/auth/google/start?next=${encodeURIComponent(next)}`;
}

export function githubSignInUrl(next: string = "/") {
  return `/api/auth/github/start?next=${encodeURIComponent(next)}`;
}

export async function sendEmailCode(email: string, lang: string) {
  return api<EmailStart>("/api/auth/email/start", { method: "POST", json: { email, lang } });
}

export async function emailSignIn(email: string, code: string) {
  await api("/api/auth/email/verify", { method: "POST", json: { email, code } });
}
