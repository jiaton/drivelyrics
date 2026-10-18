import { api } from "../../../lib/api";
import type { Schema } from "../../../lib/schema";
import { trackParams } from "../../now-playing/api/useLyrics";
import type { LyricsPayload, TrackRef } from "../../now-playing/types";

export type Recognized = Schema<"RecognizeResponse">;
export type KeyStatus = Schema<"RecognizerKeyStatus">;

export type Candidate = { title: string; artist: string; track_id: string };

/** The recognised song first, then other releases of the same audio. */
export function candidatesOf(match: Recognized): Candidate[] {
  const first = match.title && match.track_id ? [{ title: match.title, artist: match.artist ?? "", track_id: match.track_id }] : [];
  return [...first, ...(match.alternatives ?? [])];
}

export function trackOf(candidate: Candidate, durationMs: number | null | undefined): TrackRef {
  return { trackId: candidate.track_id, title: candidate.title, artist: candidate.artist, durationMs: durationMs ?? null };
}

/** Index of the first candidate with synced lyrics (0 if none has): a re-release under
 *  a translated title finds none, the original does. */
export async function firstWithLyrics(candidates: Candidate[], durationMs: number | null | undefined): Promise<number> {
  for (let i = 0; i < candidates.length; i++) {
    try {
      const body = await api<LyricsPayload>(`/api/lyrics?${trackParams(trackOf(candidates[i], durationMs))}`);
      if (body.lines.length > 0) return i;
    } catch {
      /* a provider hiccup: try the next one */
    }
  }
  return 0;
}

export const listenApi = {
  keyStatus: () => api<KeyStatus>("/api/recognize/key"),
  saveKey: (token: string) => api<KeyStatus>("/api/recognize/key", { method: "PUT", json: { token } }),
  removeKey: () => api("/api/recognize/key", { method: "DELETE" }),
  recognize: (blob: Blob, filename: string, clipMs: number) => {
    const form = new FormData();
    form.append("audio", blob, filename);
    form.append("clip_ms", String(Math.round(clipMs)));
    return api<Recognized>("/api/recognize", { method: "POST", body: form });
  },
};
