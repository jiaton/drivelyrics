import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { clearCache, readCache, writeCache } from "../../../lib/cache";
import type { Me } from "../types";

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
