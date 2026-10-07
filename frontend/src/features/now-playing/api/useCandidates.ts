import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Candidate, LyricsPayload, TrackRef } from "../types";
import { toLyricsData, trackParams, type LyricsData } from "./useLyrics";

export function useCandidates(track: TrackRef) {
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ candidates: Candidate[] }>(`/api/lyrics/candidates?${trackParams(track)}`)
      .then((body) => !cancelled && setCandidates(body.candidates))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [track]);

  return { candidates, error };
}

/** wrongSource: the source of the lyrics the reader was shown, if they say those were
 *  the wrong song (skips that source for everyone). Omit when they just prefer the
 *  picked source for this track — that only affects them. */
export async function chooseCandidate(track: TrackRef, candidate: Candidate, wrongSource?: string): Promise<LyricsData> {
  const body = await api<LyricsPayload>("/api/lyrics/choice", {
    method: "POST",
    json: {
      track_id: track.trackId,
      title: track.title,
      artist: track.artist,
      duration_ms: track.durationMs,
      source: candidate.source,
      song_id: candidate.song_id,
      wrong_source: wrongSource ?? null,
    },
  });
  return toLyricsData(body);
}
