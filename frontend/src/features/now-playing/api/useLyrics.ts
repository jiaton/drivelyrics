import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { LyricsPayload, TrackRef } from "../types";

export interface LyricsData {
  lines: LyricsPayload["lines"];
  translationLines: LyricsPayload["translation_lines"];
  source: string;
  songId: string;
  manual: boolean;
}

const EMPTY: LyricsData = { lines: [], translationLines: [], source: "", songId: "", manual: false };

export function toLyricsData(body: LyricsPayload): LyricsData {
  return { lines: body.lines, translationLines: body.translation_lines, source: body.source, songId: body.song_id, manual: body.manual };
}

export function trackParams(track: TrackRef) {
  const params = new URLSearchParams({ track_id: track.trackId, title: track.title, artist: track.artist });
  if (track.durationMs != null) params.set("duration_ms", String(track.durationMs));
  return params;
}

// Module-level cache keyed by track id + source preference: lyrics are static per song,
// and the SSE stream re-sends the same track on every poll tick, so this is what stops
// a refetch every 4 seconds instead of once per song change.
const cache = new Map<string, LyricsData>();

/**
 * `sourceKey` is whatever decides which provider the server tries first for this user
 * (see the backend's source_order): changing it must refetch. Pass track = null until
 * preferences have loaded, or the first fetch uses the defaults and is thrown away.
 */
export function useLyrics(track: TrackRef | null, sourceKey: string) {
  const [data, setData] = useState<LyricsData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trackId = track?.trackId ?? null;
  const key = trackId ? `${trackId}|${sourceKey}` : null;

  useEffect(() => {
    if (!track) {
      setData(EMPTY);
      return;
    }

    const cached = cache.get(key!);
    if (cached) {
      setData(cached);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    api<LyricsPayload>(`/api/lyrics?${trackParams(track)}`)
      .then((body) => {
        if (cancelled) return;
        const result = toLyricsData(body);
        // Don't pin an empty result: a provider outage isn't cached server-side
        // either, so the next song change back here should ask again.
        if (result.lines.length > 0) cache.set(key!, result);
        setData(result);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // Only a track or source change refetches; title/artist/duration are fixed per id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  /** After a manual pick: show it now. A pick beats every source preference, so cached
   *  results for this track under other preferences are stale too. */
  const replace = useCallback(
    (id: string, next: LyricsData) => {
      for (const k of [...cache.keys()]) if (k.startsWith(`${id}|`)) cache.delete(k);
      cache.set(`${id}|${sourceKey}`, next);
      if (id === trackId) setData(next);
    },
    [trackId, sourceKey],
  );

  return { ...data, loading, error, replace };
}
