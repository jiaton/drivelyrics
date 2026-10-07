import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { SpotifyStatus } from "../types";

export function useSpotifyStatus() {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<SpotifyStatus>("/api/spotify/status")
      .then((body) => {
        setStatus(body);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  const saveApp = useCallback(async (clientId: string, clientSecret: string) => {
    setStatus(await api<SpotifyStatus>("/api/spotify/app", { method: "PUT", json: { client_id: clientId, client_secret: clientSecret } }));
  }, []);

  const removeApp = useCallback(async () => {
    setStatus(await api<SpotifyStatus>("/api/spotify/app", { method: "DELETE" }));
  }, []);

  return { status, error, refresh, saveApp, removeApp };
}
