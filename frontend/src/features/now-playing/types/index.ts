import type { Schema } from "../../../lib/schema";

// fetched_at: unix seconds, server clock — informational only, not used for scroll timing.
export type NowPlaying = Schema<"NowPlayingResponse">;

/**
 * NowPlaying plus a client-side monotonic timestamp. `receivedAtPerf` is
 * `performance.now()` at the moment this browser received the SSE event — it lets the
 * scroll math measure "how long ago did I receive this" using only this device's own
 * clock, never comparing against the server's `fetched_at`. Comparing wall clocks
 * across a server and a car's system clock isn't something to rely on: either one
 * could be off by seconds, and `performance.now()` can't drift out of sync with itself.
 */
export type ClientNowPlaying = NowPlaying & {
  receivedAtPerf: number;
};

export type LyricLine = Schema<"LyricLineSchema">; // t: ms offset into the track

export interface TrackRef {
  trackId: string;
  title: string;
  artist: string;
  durationMs: number | null;
}

export type LyricsPayload = Schema<"LyricsResponse">;
export type Candidate = Schema<"CandidateSchema">;
