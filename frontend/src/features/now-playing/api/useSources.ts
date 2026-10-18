import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { readCache, writeCache } from "../../../lib/cache";
import type { Schema } from "../../../lib/schema";

export type Sources = Schema<"SourcesResponse">;
export type SourceName = Sources["selected"];

/** Where the user's screens get "now playing" from: their Spotify app or the feed. */
export function useSources() {
  const [sources, setSources] = useState<Sources | null>(() => readCache<Sources>("sources"));
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Sources>("/api/now-playing/sources")
      .then((body) => {
        setSources(body);
        setError(null);
        writeCache("sources", body);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  const select = useCallback(async (source: SourceName) => {
    const body = await api<Sources>("/api/now-playing/source", { method: "PUT", json: { source } });
    setSources(body);
    writeCache("sources", body);
  }, []);

  return { sources, error, refresh, select };
}
