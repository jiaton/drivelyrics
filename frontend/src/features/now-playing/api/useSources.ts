import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Schema } from "../../../lib/schema";

export type Sources = Schema<"SourcesResponse">;
export type SourceName = Sources["selected"];

/** Where the user's screens get "now playing" from: their Spotify app or the feed. */
export function useSources() {
  const [sources, setSources] = useState<Sources | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Sources>("/api/now-playing/sources")
      .then((body) => {
        setSources(body);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  const select = useCallback(async (source: SourceName) => {
    setSources(await api<Sources>("/api/now-playing/source", { method: "PUT", json: { source } }));
  }, []);

  return { sources, error, refresh, select };
}
